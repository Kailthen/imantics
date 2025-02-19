from lxml import etree as ET
from lxml.builder import E
import numpy as np
import json
import cv2
import random
from PIL import ImageDraw
from PIL import Image
import pydash

from .color import Color
from .styles import COCO
from .basic import Semantic
from .category import Category


class Annotation(Semantic):
    """
    Annotation is a marking on an image.

    This class acts as a level ontop of :class:`BBox`, :class:`Mask` and :class:`Polygons`
    to manage and generate other annotations or export formats.
    """

    @classmethod
    def from_mask(cls, mask, image=None, category=None):
        """
        Creates annotation class from a mask

        :param image: image assoicated with annotation
        :type image: :class:`Image`
        :param category: category to label annotation
        :type category: :class:`Category`
        :param mask: mask to create annotation from
        :type mask: :class:`Mask`, numpy.ndarray, list
        """
        return cls(image=image, category=category, mask=mask)

    @classmethod
    def from_bbox(cls, bbox, image=None, category=None):
        """
        Creates annotation from bounding box

        :param image: image assoicated with annotation
        :type image: :class:`Image`
        :param category: category to label annotation
        :type category: :class:`Category`
        :param polygons: bbox to create annotation from
        :type polygons: :class:`BBox`, list, tuple
        """
        return cls(image=image, category=category, bbox=bbox)

    @classmethod
    def from_polygons(cls, polygons, image=None, category=None):
        """
        Creates annotation from polygons

        Accepts following format for lists:

        .. code-block:: python

            # Segmentation Format
            [
                [x1, y1, x2, y2, x3, y3,...],
                [x1, y1, x2, y2, x3, y3,...],
                ...
            ]

        or

        .. code-block:: python

            # Point Format
            [
                [[x1, y1], [x2, y2], [x3, y3],...],
                [[x1, y1], [x2, y2], [x3, y3],...],
                ...
            ]

        *No sepcificaiton is reqiured between which
        format is used*

        :param image: image assoicated with annotation
        :type image: :class:`Image`
        :param category: category to label annotation
        :type category: :class:`Category`
        :param polygons: polygons to create annotation from
        :type polygons: :class:`Polygons`, list
        """
        return cls(image=image, category=category, polygons=polygons)

    def __init__(self, image=None, category=None, bbox=None, mask=None, polygons=None, id=0,\
                 color=None, metadata={}, score=1.0, width=0, height=0):

        assert isinstance(id, int), "id must be an integer"
        assert bbox is not None or mask is not None or polygons is not None, "you must provide a mask, bbox or polygon"

        self.image = image
        self.width = width
        self.height = height
        self.score = score


        if image is not None:
            self.width = image.width
            self.height = image.height

        self.category = category
        self.color = Color.create(color)
        self._c_bbox = BBox.create(bbox)
        self._c_mask = Mask.create(mask)
        self._c_polygons = Polygons.create(polygons)

        self._init_with_bbox = self._c_bbox is not None
        self._init_with_mask = self._c_mask is not None
        self._init_with_polygons = self._c_polygons is not None

        if (self.width + self.height) <= 0:

            if self._init_with_bbox:
                self.width, self.height = self._c_bbox.max_point

            if self._init_with_mask:
                self.height, self.width = self._c_mask.array.shape

        super(Annotation, self).__init__(id, metadata)

    @property
    def mask(self):
        """
        :class:`Mask` representation of the annotations
        """
        if not self._c_mask:

            width = self.image.width
            height = self.image.height

            if self._init_with_polygons:
                self._c_mask = self.polygons.mask(width=self.width, height=self.height)
            else:
                self._c_mask = self.bbox.mask(width=self.width, height=self.height)

        return self._c_mask

    @property
    def array(self):
        """
        Numpy array boolean mask repsentation of the annotations
        """
        return self.mask.array

    @property
    def polygons(self):
        """
        :class:`Polygons` repsentation of the annotations
        """
        if not self._c_polygons:
            if self._init_with_mask:
                self._c_polygons = self.mask.polygons()
            else:
                self._c_polygons = self.bbox.polygons()

        return self._c_polygons

    @property
    def bbox(self):
        """
        :class:`BBox` repsentation of the annotations
        """
        if not self._c_bbox:
            if self._init_with_polygons:
                self._c_bbox = self.polygons.bbox()
            else:
                self._c_bbox = self.mask.bbox()

        return self._c_bbox

    @property
    def area(self):
        """
        Qantity that expresses the extent of a two-dimensional figure
        """
        if self._init_with_mask or self._init_with_polygons:
            return self.mask.area()
        return self.bbox.area()

    def index(self, image, dataset=None):

        annotation_index = image.annotations
        category_index = image.categories

        if self.id < 1:
            self.id = len(annotation_index) + 1

        # Increment index until not found
        if dataset is None:
            if annotation_index.get(self.id):
                self.id = max(annotation_index.keys()) + 1

        else:
            if dataset._max_ann_id is None:
                if annotation_index.get(self.id):
                    self.id = max(annotation_index.keys()) + 1
                    dataset._max_ann_id = self.id

            else:
                dataset._max_ann_id += 1
                self.id = dataset._max_ann_id

        annotation_index[self.id] = self

        # Category indexing should be case insenstive
        category_name = self.category.name.lower()

        # Check if category exists
        category_found = category_index.get(category_name)
        if category_found:
            # Update category
            self.category = category_found
        else:
            # Index category
            category_index[category_name] = self.category

    def set_image(self, image):
        """
        Sets the annotaiton image information

        :type image: :class:`Image`
        """
        self.image = image

        if image is None:
            return

        self.width = self.image.width
        self.height = self.image.height

        # Mask needs to be re-generated
        # self._c_mask = None

    @property
    def size(self):
        """
        Tuple of width and height
        """
        return (self.width, self.height)

    def truncated(self):
        return len(self.polygons.segmentation) > 1

    def contains(self, item):
        if isinstance(item, Annotation):
            item = item.mask
        return self.mask.contains(item)

    def __contains__(self, item):
        return self.contains(item)

    def coco(self, include=True):
        """
        Generates COCO format of annotation

        :param include: True to include all COCO formats, Fale to generate just
                        annotation format
        :type include: bool
        :returns: COCO format of annotation
        :rtype: dict
        """
        image_id = self.image.id if self.image else None
        category_id = self.category.id if self.category else None

        annotation = {
            'id': self.id,
            'image_id': image_id,
            'category_id': category_id,
            'width': self.width,
            'height': self.height,
            'area': int(self.area),
            'segmentation': self.polygons.segmentation,
            'bbox': self.bbox.bbox(style=BBox.XYWH),
            'metadata': self.metadata,
            'color': self.color.hex,
            'iscrowd': 0,
            'isbbox': self._init_with_bbox

        }

        i = 0
        while i < len(annotation['segmentation']):
            if len(annotation['segmentation'][i]) == 2:
                # discard segmentation that is only a point
                annotation['segmentation'].pop(i)
            elif len(annotation['segmentation'][i]) == 4:
                # create another point in the middle of segmentation to
                # avoid bug when using pycocotools, which thinks that a
                # 4 value segmentation mask is a bounding box
                polygon = annotation['segmentation'][i]
                x1, y1, x2, y2 = polygon
                if x2 == x1:
                    x = x1
                    y = (y2 + y1) // 2
                elif y2 == y1:
                    x = (x2 + x1) // 2
                    y = y1
                else:
                    a = (y2 - y1) / (x2 - x1)
                    b = y1 - a*x1
                    x = (x2 + x1) // 2
                    y = int(round(a*x + b))

                new_segmentation = polygon[:2] + [x, y] + polygon[2:]
                annotation['segmentation'][i] = new_segmentation
                i += 1

        if include:
            image = category = {}
            if self.image:
                image = self.image.coco(include=False)

            if self.category:
                category = self.category.coco()

            return {
                'categories': [category],
                'images': [image],
                'annotations': [annotation]
            }

        return annotation

    def yolo(self, as_string=True):
        """
        Generates YOLO format of annotation (using the bounding box)

        :param as_string: return string (true) or tuple (false) representation
        :type as_string: bool
        :returns: YOLO repersentation of annotation
        :rtype: str, tuple
        """
        height = self.bbox.height / self.image.height
        width = self.bbox.width / self.image.width
        x = self.bbox._xmin / self.image.width
        y = self.bbox._ymin / self.image.height
        label = self.category.id

        if as_string:
            return "{} {:.5f} {:.5f} {:.5f} {:.5f}".format(label, x, y, width, height)
        else:
            return label, x, y, width, height

    def voc(self):

        element = E('object',
            E('name', self.category.name),
            E('pose', self.metadata.get('pose', 'Unspecified')),
            E('truncated', str(1 if self.truncated() else 0)),
            E('difficult', str(self.metadata.get('difficult', 0))),
            E('bndbox',
                E('xmin', str(self.bbox._xmin)),
                E('ymin', str(self.bbox._ymin)),
                E('xmax', str(self.bbox._xmax)),
                E('ymax', str(self.bbox._ymax)),
            )
        )

        return element
    
    @classmethod
    def from_pgl(cls, pgl_obj:dict, image:Image.Image = None):
        image_field = pydash.get(pgl_obj, 'object_data.image', None)
        bbox_field = pydash.get(pgl_obj, 'object_data.bbox', None)
        if image_field is not None:
            # TODO 
            return cls(image=image, category=None, mask=None)
        elif bbox_field is not None:
            box_arr = pydash.get(pgl_obj, 'object_data.bbox[0].val', None)
            category = None
            cate = pydash.get(pgl_obj, 'type', None)
            if cate is not None:
                category = Category(name=cate)
            
            scor = 1.0
            num_attrs = pydash.get(pgl_obj, 'object_data.bbox[0].attributes.num', None)
            if num_attrs is not None:
                for attr in num_attrs:
                    if attr['name'] == 'score':
                        scor = attr['val']
                        break
            return cls(image=image, category=category, bbox=BBox.create(box_arr, style=BBox.CXCYWH), score=scor)
    
    def pgl(self, rle=False):
        """
        to openlabel format

        Args:
            rle (bool, optional): Convert Binary Mask to RLE format, save to object_data.image. Defaults to False.
        """
        def _box(bbox, score):
            return [
                        {
                            "val": bbox,
                            "attributes": {
                                "num": [
                                    {
                                        "name": "score",
                                        "val": score
                                    }
                                ],
                            }
                        }
                    ]
        def _polys(mask, score):
                return [{
                "closed": True,
                "mode": "MODE_POLY2D_ABSOLUTE",
                "val": poly.flatten(),
                "attributes": {
                    "num": [
                        {
                            "name": "score",
                            "val": score
                        }
                    ],
                }
            } for poly in mask.polygons().points]
        def _rle(mask, score):
            return {
                "val": ",".join([str(round(c, 3)) for c in mask.to_rle()['counts']]),
                "mime_type": "image/png",
                "encoding": "rle",
                "attributes": {
                    "num": [
                        {
                            "name": "score",
                            "val": score
                        }
                    ],
                }
            }
        category_name = self.category.name if self.category else None
        bbox = list(self.bbox.bbox(style=BBox.CXCYWH))
        if self._init_with_bbox:
            entity = {
                "type": category_name,
                "object_data": {
                    "bbox": _box(bbox, self.score)
                }
            }
        elif self._init_with_mask:
            entity = {
                "type": category_name,
                "object_data": {
                    "bbox": _box(bbox, self.score),
                    'poly2d': _polys(self.mask, self.score),
                    'image': _rle(self.mask, self.score) if rle else None
                }
            }
        elif self._init_with_polygons:
           pass
        return entity

    def save(self, file_path, style=COCO):
        with open(file_path, 'w') as fp:
            json.dump(self.export(style=style), fp)
            
    def draw(self, image:Image.Image):
        empty_image = Image.new('RGBA', image.size, color=(0, 0, 0, 0))
        image_draw = ImageDraw.Draw(empty_image)
        if self._init_with_bbox:
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 153)

            text = f"{self.score:.3f}"
            if self.category is not None:
                color = (*(self.category.color.rgb), 153)
                text = f"{self.category.name} {text}"
            xyxy = self.bbox.bbox(style=BBox.XYXY)
            image_draw.rectangle(((xyxy[0], xyxy[1]), (xyxy[2], xyxy[3])), outline=color,  width=2)
            color = (30, 144, 255, 153)
            image_draw.text((xyxy[0], xyxy[1]), text, fill=color)
        n_image = image.convert('RGBA')
        n_image.alpha_composite(empty_image)
        return n_image

class BBox:
    """
    Bounding Box is an enclosing retangular box for a image marking
    """

    #: Value types of :class:`BBox`
    INSTANCE_TYPES = (np.ndarray, list, tuple)

    #: Bounding box format style [x1, y1, x2, y2]
    XYXY = 'xyxy'

    #: Bounding box format style [x1, y1, width, height]
    XYWH = 'xywh'
    
    #: Bounding box format style [center_x, center_y, width, height]
    CXCYWH = 'cxcywh'

    @classmethod
    def from_mask(cls, mask):
        """
        Creates :class:`BBox` from mask

        :param mask: object to generate bounding box
        :type mask: :class:`Mask`, numpy.ndarray, list
        :returns: :class:`BBox` repersentation
        """
        return Mask.create(mask).bbox()

    @classmethod
    def from_polygons(cls, polygons):
        """
        Creates :class:`BBox` from polygons

        :param polygons: object to generate bounding box
        :type polygons: :class:`Polygons`, list
        :returns: :class:`BBox` repersentation
        """
        return Polygons.create(polygons).bbox()

    @classmethod
    def create(cls, bbox, style=None):
        """
        Creates :class:`BBox`

        Recommend over the use of ``__init__``.
        """
        if isinstance(bbox, BBox.INSTANCE_TYPES):
            return BBox(bbox, style=style)

        if isinstance(bbox, BBox):
            return bbox

        return None

    @classmethod
    def empty(cls):
        """
        :returns: Empty :class:`BBox` object
        """
        return BBox((0, 0, 0, 0))

    _c_polygons = None
    _c_mask = None

    def __init__(self, bbox, style=None):

        assert len(bbox) == 4

        self.style = style if style else BBox.XYXY

        self._xmin = int(bbox[0])
        self._ymin = int(bbox[1])

        if self.style == self.XYXY:
            self._xmax = int(bbox[2])
            self._ymax = int(bbox[3])
            self.width = self._xmax - self._xmin
            self.height = self._ymax - self._ymin

        if self.style == self.XYWH:
            self.width = int(bbox[2])
            self.height = int(bbox[3])
            self._xmax = self._xmin + self.width
            self._ymax = self._ymin + self.height
            
        if self.style == self.CXCYWH:
            cx = bbox[0]
            cy = bbox[1]
            self.width = int(bbox[2])
            self.height = int(bbox[3])
            
            self._xmin = cx - self.width / 2
            self._ymin = cy - self.height / 2
            self._xmax = self._xmin + self.width
            self._ymax = self._ymin + self.height

    def area(self):
        return self.width * self.height

    def bbox(self, style='xyxy'):
        """
        Generates tuple repersentation of bounding box

        :param style: stlye to generate bounding box (defaults: XYXY)
        :returns: tuple of bounding box with specified style
        """
        # style = style if style else self.style
        if style is None:
            style = self.XYXY
    
        if style == self.XYXY:
            return self._xmin, self._ymin, self._xmax, self._ymax
        elif style == self.XYWH:
            return self._xmin, self._ymin, self.width, self.height
        elif style == self.CXCYWH:
            cx = self._xmin + self.width / 2
            cy = self._ymin + self.height / 2
            return cx, cy, self.width, self.height
        else:
            raise ValueError('Style {} is not supported'.format(style))

    def polygons(self):
        """
        Returns or generates :class:`Polygons` representation of bounding box.

        :returns: Polygon representation
        :rtype: :class:`Polygons`
        """
        if not self._c_polygons:
            polygon = self.top_left + self.top_right \
                    + self.bottom_right + self.bottom_left
            return Polygons([polygon])
        return self._c_polygons

    def mask(self, width=None, height=None):
        """
        Returns or generates :class:`Mask` representation of bounding box.

        :returns: Mask representation
        :rtype: :class:`Mask`
        """
        if not self._c_mask:

            mask = np.zeros((height, width))
            mask[self.min_point[1]:self.max_point[1], self.min_point[0]:self.max_point[0]] = 1

            self._c_mask = Mask(mask)

        return self._c_mask

    @property
    def min_point(self):
        """
        Minimum points of the bounding box (x1, y1)
        """
        return self._xmin, self._ymin

    @property
    def max_point(self):
        """
        Maximum points of the bounding box (x2, y2)
        """
        return self._xmax, self._ymax

    @property
    def top_right(self):
        """
        Tops right point of the bounding box::

            [ ]------[X]
             |        |
             |        |
            [ ]------[ ]

        """
        return self._xmax, self._ymin

    @property
    def top_left(self):
        """
        Tops left point of the bounding box::

            [X]------[ ]
             |        |
             |        |
            [ ]------[ ]

        """
        return self._xmin, self._ymin

    @property
    def bottom_right(self):
        """
        Tops left point of the bounding box::

            [ ]------[ ]
             |        |
             |        |
            [ ]------[X]

        """
        return self._xmax, self._ymax

    @property
    def bottom_left(self):
        """
        Tops left point of the bounding box::

            [ ]------[ ]
             |        |
             |        |
            [X]------[ ]

        """
        return self._xmin, self._ymax

    @property
    def size(self):
        """
        Width and height as a tuple (width, height)
        """
        return self.width, self.height

    def _compute_size(self):
        self.width = self._xmax - self._xmin
        self.height = self._ymax - self._ymin

    def __getitem__(self, item):
        return self.bbox()[item]

    def __repr__(self):
        return repr(self.bbox())

    def __str__(self):
        return str(self.bbox())

    def __eq__(self, other):
        if isinstance(other, self.INSTANCE_TYPES):
            other = BBox(other)

        if isinstance(other, BBox):
            return np.array_equal(self.bbox(style=self.XYXY), other.bbox(style=self.XYXY))

        return False


class Polygons:

    #: Polygon instance types
    INSTANCE_TYPES = (list, tuple)

    @classmethod
    def from_mask(cls, mask):
        """
        Creates :class:`Polygons` from mask

        :param mask: object to generate mask
        :type mask: :class:`Mask`, numpy.ndarray, list
        :returns: :class:`Polygons` repersentation
        """
        return Mask.create(mask).polygons()

    @classmethod
    def from_bbox(cls, bbox, style=None):
        """
        Creates :class:`Polygons` from bounding box

        :param bbox: object to generate bounding box
        :type bbox: :class:`BBox`, list, tuple
        :returns: :class:`Polygons` repersentation
        """
        return BBox.create(bbox).polygons()

    @classmethod
    def create(cls, polygons):

        if isinstance(polygons, Polygons.INSTANCE_TYPES):
            return Polygons(polygons)

        if isinstance(polygons, Polygons):
            return polygons

        return None

    _c_bbox = None
    _c_mask = None

    _c_points = None
    _c_segmentation = None

    def __init__(self, polygons):
        self.polygons = [np.array(polygon).flatten() for polygon in polygons]

    def mask(self, width=None, height=None):
        """
        Returns or generates :class:`Mask` representation of polygons.

        :returns: Mask representation
        :rtype: :class:`Mask`
        """
        if not self._c_mask:

            size = height, width if height and width else self.bbox().max_point
            # Generate mask from polygons

            mask = np.zeros(size)
            mask = cv2.fillPoly(mask, self.points, 1)

            self._c_mask = Mask(mask)
            self._c_mask._c_polygons = self

        return self._c_mask

    def bbox(self):
        """
        Returns or generates :class:`BBox` representation of polygons.

        :returns: Bounding Box representation
        :rtype: :class:`BBox`
        """
        if not self._c_bbox:

            y_min = x_min = float('inf')
            y_max = x_max = float('-inf')

            for point_list in self.points:
                minx, miny = np.min(point_list, axis=0)
                maxx, maxy = np.max(point_list, axis=0)

                y_min = min(miny, y_min)
                x_min = min(minx, x_min)
                y_max = max(maxy, y_max)
                x_max = max(maxx, x_max)

            self._c_bbox = BBox((x_min, y_min, x_max, y_max))
            self._c_bbox._c_polygons = self

        return self._c_bbox

    def simplify(self):
        # TODO: Write simplification algotherm
        self._c_points = None

    @property
    def points(self):
        """
        Returns polygon in point format::

            [
                [[x1, y1], [x2, y2], [x3, y3], ...],
                [[x1, y1], [x2, y2], [x3, y3], ...],
                ...
            ]

        """
        if not self._c_points:
            self._c_points = [
                np.array(point).reshape(-1, 2).round().astype(int)
                for point in self.polygons
            ]

        return self._c_points

    @property
    def segmentation(self):
        """
        Returns polygon in segmentation format::

            [
                [x1, y1, x2, y2, x3, y3, ...],
                [x1, y1, x2, y2, x3, y3, ...],
                ...
            ]

        """
        if not self._c_segmentation:
            self._c_segmentation = [polygon.tolist() for polygon in self.polygons]

        return self._c_segmentation

    def draw(self, image, color=None, thickness=3):
        """
        Draws the polygons to the image array of shape (width, height, 3)

        *This function modifies the image array*

        :param color: RGB color repersentation
        :type color: tuple, list
        :param thickness: pixel thickness of box
        :type thinkness: int
        """
        color = Color.create(color).rgb
        image_copy = image.copy()
        cv2.polylines(image_copy, self.points, True, color, thickness)
        return image_copy

    def __eq__(self, other):
        if isinstance(other, self.INSTANCE_TYPES):
            other = Polygons(other)

        if isinstance(other, Polygons):
            for i in range(len(self.polygons)):
                if not np.array_equal(self[i], other[i]):
                    return False
            return True

        return False

    def __getitem__(self, key):
        return self.polygons[key]

    def __repr__(self):
        return repr(self.polygons)


class Mask:
    """
    Mask class
    """

    INSTANCE_TYPES = (np.ndarray,)

    @classmethod
    def from_polygons(cls, polygons):
        return Polygons.create(polygons).mask()

    @classmethod
    def from_bbox(cls, bbox):
        return BBox.create(bbox).mask()

    @classmethod
    def create(cls, mask):
        if isinstance(mask, Mask.INSTANCE_TYPES):
            return Mask(mask)

        if isinstance(mask, Mask):
            return mask

        return None

    _c_bbox = None
    _c_polygons = None

    def __init__(self, array):
        self.array = np.array(array, dtype=bool)
        
    def to_rle(self) -> dict:
        """mask to rle
        Returns:
            dict: rle object
        """
        binary_mask = self.array
        rle = {"counts": [], "size": list(binary_mask.shape)}

        flattened_mask = binary_mask.ravel(order="F")
        diff_arr = np.diff(flattened_mask)
        nonzero_indices = np.where(diff_arr != 0)[0] + 1
        lengths = np.diff(np.concatenate(([0], nonzero_indices, [len(flattened_mask)])))

        # the odd counts are always the numbers of zeros
        if flattened_mask[0] == 1:
            lengths = np.concatenate(([0], lengths))

        rle["counts"] = lengths.tolist()

        return rle

    def bbox(self):
        """
        Returns or generates :class:`BBox` representation of mask.

        :returns: Bounding Box representation
        :rtype: :class:`BBox`
        """
        if not self._c_bbox:

            # Generate bbox from mask
            rows = np.any(self.array, axis=1)
            cols = np.any(self.array, axis=0)

            if not np.any(rows) or not np.any(cols):
                return BBox.empty()

            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]

            self._c_bbox = BBox((cmin, rmin, cmax, rmax))
            self._c_bbox._c_mask = self

        return self._c_bbox

    def polygons(self):
        """
        Returns or generates :class:`Polygons` representation of mask.

        :returns: Polygons representation
        :rtype: :class:`Polygons`
        """
        if not self._c_polygons:

            # Generate polygons from mask
            mask = self.array.astype(np.uint8)
            mask = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
            polygons = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE, offset=(-1, -1))
            polygons = polygons[0] if len(polygons) == 2 else polygons[1]
            polygons = [polygon.flatten() for polygon in polygons]

            self._c_polygons = Polygons(polygons)
            self._c_polygons._c_mask = self

        return self._c_polygons

    def union(self, other):
        """
        Unites the array of the specified mask with this mask’s array and returns the result as a new mask.

        :param other: mask to unite with
        :type other: :class:`Mask`, numpy.ndarray
        :return: resulting :class:`Mask`
        """
        if isinstance(other, np.ndarray):
            other = Mask(other)

        return Mask(np.logical_or(self.array, other.array))

    def __add__(self, other):
        return self.union(other)

    def intersect(self, other):
        """
        Intersects the array of the specified mask with this masks’s array
        and returns the result as a new mask.

        :param other: mask to intersect with
        :type other: :class:`Mask`, numpy.ndarray
        :return: resulting :class:`Mask`
        """
        if isinstance(other, np.ndarray):
            other = Mask(other)

        return Mask(np.logical_and(self.array, other.array))

    def __mul__(self, other):
        return self.intersect(other)

    def iou(self, other):
        """
        Intersect over union value of the specified masks

        :param other: mask to compute value with
        :type other: :class:`Mask`, numpy.ndarray
        :return: resulting float value
        """
        i = self.intersect(other).sum()
        u = self.union(other).sum()

        if i == 0 or u == 0:
            return 0

        return i / float(u)

    def invert(self):
        """
        Inverts current mask

        :return: resulting :class:`Mask`
        """
        return Mask(np.invert(self.array))

    def __invert__(self):
        return self.invert()

    def draw(self, image, color=None, alpha=0.5):
        """
        Draws current mask to the image array of shape (width, height, 3)

        *This function modifies the image array*

        :param color: RGB color repersentation
        :type color: tuple, list
        :param alpha: opacity of mask
        :type alpha: float
        """
        color = Color.create(color).rgb
        image_copy = image.copy()
        for c in range(3):
            image_copy[:, :, c] = np.where(
                self.array,
                image_copy[:, :, c] * (1 - alpha) + alpha * color[c],
                image_copy[:, :, c]
            )
        return image_copy

    def subtract(self, other):
        """
        Subtracts the array of the specified mask from this masks’s array and
        returns the result as a new mask.

        :param other: mask (or numpy array) to subtract
        :retrn: resulting mask
        """
        if isinstance(other, np.ndarray):
            other = Mask(other)

        return self.intersect(other.invert())

    def __sub__(self, other):
        return self.subtract(other)

    def contains(self, item):
        """
        Checks whether a point (tuple), array or mask is within current mask.

        Note: Masks and arrays must be fully contained to return True

        :param item: object to check
        :return: bool if item is contained
        """
        if isinstance(item, tuple):
            array = self.array
            for i in item:
                array = array[i]
            return array

        if isinstance(item, np.ndarray):
            item = Mask(item)

        if isinstance(item, Mask):
            return self.intersect(item).area() > 0

        return False

    def __contains__(self, item):
        return self.contains(item)

    def match(self, item, threshold=0.5):
        """
        Given a overlap threashold determines if masks match

        :param item: item to compare with
        :type item: :class:`Mask`
        :param threshold: max amount of overlap (percentage)
        :returns: boolean determining if the items match
        """
        return self.iou(item) >= threshold

    def sum(self):
        return self.array.sum()

    def area(self):
        return self.sum()

    def __getitem__(self, key):
        return self.array[key]

    def __setitem__(self, key, value):
        self.array[key] = value

    def __eq__(self, other):
        if isinstance(other, (np.ndarray, list)):
            other = Mask(other)

        if isinstance(other, Mask):
            return np.array_equal(self.array, other.array)

        return False

    def __repr__(self):
        return repr(self.array)


__all__ = ["Annotation", "BBox", "Mask", "Polygons"]
