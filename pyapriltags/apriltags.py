#!/usr/bin/env python

"""Python wrapper for C version of apriltags. This program creates two
classes that are used to detect apriltags and extract information from
them. Using this module, you can identify all apriltags visible in an
image, and get information about the location and orientation of the
tags.

Original author: Isaac Dulin, Spring 2016
Updates: Matt Zucker, Fall 2016
Apriltags 3 version: Aleksandar Petrov, Spring 2019
Current maintainer: Will Barber

"""
import ctypes
import os
import sys
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union

import numpy

dir_path = os.path.dirname(os.path.realpath(__file__))


######################################################################

# pylint: disable=R0903

class _ImageU8(ctypes.Structure):
    """Wraps image_u8 C struct."""
    _fields_ = [
        ('width', ctypes.c_int),
        ('height', ctypes.c_int),
        ('stride', ctypes.c_int),
        ('buf', ctypes.POINTER(ctypes.c_uint8))
    ]


class _Matd(ctypes.Structure):
    """Wraps matd C struct."""
    _fields_ = [
        ('nrows', ctypes.c_int),
        ('ncols', ctypes.c_int),
        ('data', ctypes.POINTER(ctypes.c_double)),
    ]


class _ZArray(ctypes.Structure):
    """Wraps zarray C struct."""
    _fields_ = [
        ('el_sz', ctypes.c_size_t),
        ('size', ctypes.c_int),
        ('alloc', ctypes.c_int),
        ('data', ctypes.c_void_p)
    ]


class _ApriltagFamily(ctypes.Structure):
    """Wraps apriltag_family C struct."""
    _fields_ = [
        ('ncodes', ctypes.c_uint32),
        ('codes', ctypes.POINTER(ctypes.c_uint64)),
        ('width_at_border', ctypes.c_int),
        ('total_width', ctypes.c_int),
        ('reversed_border', ctypes.c_bool),
        ('nbits', ctypes.c_uint32),
        ('bit_x', ctypes.POINTER(ctypes.c_int32)),
        ('bit_y', ctypes.POINTER(ctypes.c_int32)),
        ('h', ctypes.c_int32),
        ('name', ctypes.c_char_p),
    ]


class _ApriltagDetection(ctypes.Structure):
    """Wraps apriltag_detection C struct."""
    _fields_ = [
        ('family', ctypes.POINTER(_ApriltagFamily)),
        ('id', ctypes.c_int),
        ('hamming', ctypes.c_int),
        ('decision_margin', ctypes.c_float),
        ('H', ctypes.POINTER(_Matd)),
        ('c', ctypes.c_double * 2),
        ('p', (ctypes.c_double * 2) * 4)
    ]


class _ApriltagDetector(ctypes.Structure):
    """Wraps apriltag_detector C struct."""
    _fields_ = [
        ('nthreads', ctypes.c_int),
        ('quad_decimate', ctypes.c_float),
        ('quad_sigma', ctypes.c_float),
        ('refine_edges', ctypes.c_int),
        ('decode_sharpening', ctypes.c_double),
        ('debug', ctypes.c_int)
    ]


class _ApriltagDetectionInfo(ctypes.Structure):
    """Wraps apriltag_detection_info C struct."""
    _fields_ = [
        ('det', ctypes.POINTER(_ApriltagDetection)),
        ('tagsize', ctypes.c_double),
        ('fx', ctypes.c_double),
        ('fy', ctypes.c_double),
        ('cx', ctypes.c_double),
        ('cy', ctypes.c_double)
    ]


class _ApriltagPose(ctypes.Structure):
    """Wraps apriltag_pose C struct."""
    _fields_ = [
        ('R', ctypes.POINTER(_Matd)),
        ('t', ctypes.POINTER(_Matd))
    ]


######################################################################

def _ptr_to_array2d(datatype, ptr, rows, cols):
    array_type = (datatype * cols) * rows
    array_buf = array_type.from_address(ctypes.addressof(ptr))
    return numpy.ctypeslib.as_array(array_buf, shape=(rows, cols))


def _image_u8_get_array(img_ptr):
    return _ptr_to_array2d(ctypes.c_uint8,
                           img_ptr.contents.buf.contents,
                           img_ptr.contents.height,
                           img_ptr.contents.stride)


def _matd_get_array(mat_ptr):
    return _ptr_to_array2d(ctypes.c_double,
                           mat_ptr.contents.data.contents,
                           int(mat_ptr.contents.nrows),
                           int(mat_ptr.contents.ncols))


def zarray_get(za, idx, ptr):
    # memcpy(p, &za->data[idx*za->el_sz], za->el_sz);
    #
    # p                           = ptr
    # za->el_sz                   = za.contents.el_sz
    # &za->data[idx*za->el_sz]    = za.contents.data+idx*za.contents.el_sz

    ctypes.memmove(ptr, za.contents.data + idx * za.contents.el_sz, za.contents.el_sz)


######################################################################

class Detection(NamedTuple):
    """
    Combined pythonic wrapper for apriltag_detection and apriltag_pose
    """
    tag_family: bytes
    tag_id: int
    hamming: int
    decision_margin: float
    homography: numpy.ndarray
    center: numpy.ndarray
    corners: numpy.ndarray
    pose_R: Optional[numpy.ndarray] = None
    pose_t: Optional[numpy.ndarray] = None
    pose_err: Optional[float] = None
    tag_size: Optional[float] = None

    def __str__(self):
        return ('Detection object:' +
                '\ntag_family = ' + str(self.tag_family) +
                '\ntag_id = ' + str(self.tag_id) +
                '\ntag_size = ' + str(self.tag_size) +
                '\nhamming = ' + str(self.hamming) +
                '\ndecision_margin = ' + str(self.decision_margin) +
                '\nhomography = ' + str(self.homography) +
                '\ncenter = ' + str(self.center) +
                '\ncorners = ' + str(self.corners) +
                '\npose_R = ' + str(self.pose_R) +
                '\npose_t = ' + str(self.pose_t) +
                '\npose_err = ' + str(self.pose_err) + '\n')

    def __repr__(self):
        return self.__str__()


######################################################################

class Detector(object):
    """
    Pythonic wrapper for apriltag_detector.

    families:           Tag families, separated with a space, default: tag36h11
    nthreads:           Number of threads, default: 1
    quad_decimate:      Detection of quads can be done on a lower-resolution image, improving
                        speed at a cost of pose accuracy and a slight decrease in detection
                        rate. Decoding the binary payload is still done at full resolution,
                        default: 2.0
    quad_sigma:         What Gaussian blur should be applied to the segmented image (used for
                        quad detection?)  Parameter is the standard deviation in pixels.
                        Very noisy images benefit from non-zero values (e.g. 0.8),
                        default: 0.0
    refine_edges:       When non-zero, the edges of the each quad are adjusted to "snap to"
                        strong gradients nearby. This is useful when decimation is employed,
                        as it can increase the quality of the initial quad estimate
                        substantially. Generally recommended to be on (1). Very
                        computationally inexpensive. Option is ignored if quad_decimate = 1,
                        default: 1
    decode_sharpening:  How much sharpening should be done to decoded images? This can help
                        decode small tags but may or may not help in odd lighting conditions
                        or low light conditions, default = 0.25
    searchpath:         Where to look for the Apriltag 3 library, must be a list,
                        default: ['apriltags']
    debug:              If 1, will save debug images. Runs very slow, default: 0
    """

    _SUPPORTED_FAMILIES = (
        'tag16h5',
        'tag25h9',
        'tag36h11',
        'tagCircle21h7',
        'tagCircle49h12',
        'tagCustom48h12',
        'tagStandard41h12',
        'tagStandard52h13',
    )

    def __init__(self,
                 families: str = 'tag36h11',
                 nthreads: int = 1,
                 quad_decimate: float = 2.0,
                 quad_sigma: float = 0.0,
                 refine_edges: int = 1,
                 decode_sharpening: float = 0.25,
                 debug: int = 0,
                 searchpath: List[str] = ['apriltags', '.', dir_path]):

        # Parse the parameters
        self.params: Dict[str, Any] = dict()
        self.params['families'] = families.split()
        self.params['nthreads'] = nthreads
        self.params['quad_decimate'] = quad_decimate
        self.params['quad_sigma'] = quad_sigma
        self.params['refine_edges'] = refine_edges
        self.params['decode_sharpening'] = decode_sharpening
        self.params['debug'] = debug

        # detect OS to get extension for DLL
        platform = sys.platform
        if platform.startswith('linux'):
            extension = '.so'
        elif platform.startswith('darwin'):
            extension = '.dylib'
        elif platform == 'win32':
            extension = '.dll'
        else:
            raise NotImplementedError(f"The platform {platform} is not supported")

        filename = 'libapriltag' + extension

        self.libc = None
        self.tag_detector = None
        self.tag_detector_ptr = None

        for path in searchpath:
            relpath = os.path.join(os.path.dirname(__file__), path, filename)
            if os.path.exists(relpath):
                self.libc = ctypes.CDLL(relpath)
                break

        # if full path not found just try opening the raw filename;
        # this should search whatever paths dlopen is supposed to
        # search.
        if self.libc is None:
            self.libc = ctypes.CDLL(os.path.join(os.path.dirname(__file__), filename))

        if self.libc is None:
            raise RuntimeError('could not find DLL named ' + filename)

        # setup the return types for all the functions used from the DLL
        self._setup_restype()

        # create the c-_apriltag_detector object
        self.tag_detector_ptr = self.libc.apriltag_detector_create()

        # create the family
        self.tag_families = dict()
        for family in self.params['families']:
            if family in self._SUPPORTED_FAMILIES:
                # Call the family's create method
                self.tag_families[family] = getattr(self.libc, f'{family}_create')()
                self.libc.apriltag_detector_add_family_bits(
                    self.tag_detector_ptr,
                    self.tag_families[family],
                    2,
                )
            else:
                raise Exception(
                    'Unrecognized tag family name. Use e.g. \'tag36h11\'.\n')

        # configure the parameters of the detector
        self.tag_detector_ptr.contents.nthreads = int(self.params['nthreads'])
        self.tag_detector_ptr.contents.quad_decimate = float(self.params['quad_decimate'])
        self.tag_detector_ptr.contents.quad_sigma = float(self.params['quad_sigma'])
        self.tag_detector_ptr.contents.refine_edges = int(self.params['refine_edges'])
        self.tag_detector_ptr.contents.decode_sharpening = int(self.params['decode_sharpening'])  # noqa: E501
        self.tag_detector_ptr.contents.debug = int(self.params['debug'])

    def _setup_restype(self):
        """Setup the return types for all the functions used from the DLL."""
        # Functions used in __init__
        self.libc.apriltag_detector_create.restype = ctypes.POINTER(_ApriltagDetector)
        self.libc.apriltag_detector_add_family_bits.restype = None
        self.libc.apriltag_detector_destroy.restype = None

        # Tag family constructors and destructors
        for family in self._SUPPORTED_FAMILIES:
            getattr(self.libc, f'{family}_create').restype = ctypes.POINTER(_ApriltagFamily)
            getattr(self.libc, f'{family}_destroy').restype = None

        # Functions used by detect()
        self.libc.apriltag_detector_detect.restype = ctypes.POINTER(_ZArray)
        self.libc.estimate_tag_pose.restype = ctypes.c_double
        self.libc.matd_destroy.restype = None
        self.libc.matd_destroy.restype = None
        self.libc.image_u8_destroy.restype = None
        self.libc.apriltag_detections_destroy.restype = None
        self.libc.image_u8_create.restype = ctypes.POINTER(_ImageU8)

    def __del__(self):
        if self.tag_detector_ptr is not None:
            # destroy the detector
            self.libc.apriltag_detector_destroy(self.tag_detector_ptr)

            # destroy the tag families
            for family, tf in self.tag_families.items():
                if family in self._SUPPORTED_FAMILIES:
                    # Call the family's destroy method
                    getattr(self.libc, f'{family}_destroy')(tf)

    def detect(
        self, img: numpy.ndarray, estimate_tag_pose: bool = False,
        camera_params: Union[numpy.ndarray, Tuple[float, float, float, float], None] = None,
        tag_size: Union[float, None, Dict[int, float]] = None,
    ) -> List[Detection]:
        """
        Run detectons on the provided image. The image must be a grayscale
        image of type numpy.uint8.
        """
        assert len(img.shape) == 2
        assert img.dtype == numpy.uint8

        c_img = self._convert_image(img)

        return_info = []

        if self.libc is None:
            raise RuntimeError('No DLL found')

        # detect apriltags in the image
        detections = self.libc.apriltag_detector_detect(self.tag_detector_ptr, c_img)

        apriltag = ctypes.POINTER(_ApriltagDetection)()

        for i in range(0, detections.contents.size):

            # extract the data for each apriltag that was identified
            zarray_get(detections, i, ctypes.byref(apriltag))

            tag = apriltag.contents

            homography = _matd_get_array(tag.H).copy()
            center = numpy.ctypeslib.as_array(tag.c, shape=(2,)).copy()
            corners = numpy.ctypeslib.as_array(tag.p, shape=(4, 2)).copy()

            if estimate_tag_pose:
                if camera_params is None:
                    raise Exception(
                        'camera_params must be provided to detect if estimate_tag_pose is '
                        'set to True')
                if tag_size is None:
                    raise Exception(
                        'tag_size must be provided to detect if estimate_tag_pose is set to '
                        'True')

                if isinstance(tag_size, dict):
                    individual_tag_size = tag_size.get(tag.id, 0)
                else:
                    individual_tag_size = tag_size

                if individual_tag_size != 0:
                    camera_fx, camera_fy, camera_cx, camera_cy = [c for c in camera_params]

                    info = _ApriltagDetectionInfo(det=apriltag,
                                                  tagsize=individual_tag_size,
                                                  fx=camera_fx,
                                                  fy=camera_fy,
                                                  cx=camera_cx,
                                                  cy=camera_cy)
                    pose = _ApriltagPose()

                    err = self.libc.estimate_tag_pose(ctypes.byref(info), ctypes.byref(pose))

                    pose_R = _matd_get_array(pose.R).copy()
                    pose_t = _matd_get_array(pose.t).copy()
                    pose_err = err

                    self.libc.matd_destroy(pose.R)

                    self.libc.matd_destroy(pose.t)
                else:
                    pose_R = None
                    pose_t = None
                    pose_err = None
            else:
                pose_R = None
                pose_t = None
                pose_err = None
                individual_tag_size = None

            detection = Detection(
                tag_family=ctypes.string_at(tag.family.contents.name),
                tag_id=tag.id,
                hamming=tag.hamming,
                decision_margin=tag.decision_margin,
                homography=homography,
                center=center,
                corners=corners,
                pose_R=pose_R,
                pose_t=pose_t,
                pose_err=pose_err,
                tag_size=individual_tag_size,
            )

            # append this dict to the tag data array
            return_info.append(detection)

        self.libc.image_u8_destroy(c_img)

        self.libc.apriltag_detections_destroy(detections)

        return return_info

    def _convert_image(self, img):
        height = img.shape[0]
        width = img.shape[1]

        c_img = self.libc.image_u8_create(width, height)

        tmp = _image_u8_get_array(c_img)

        # copy the opencv image into the destination array, accounting for the
        # difference between stride & width.
        tmp[:, :width] = img

        # tmp goes out of scope here but we don't care because
        # the underlying data is still in c_img.
        return c_img
