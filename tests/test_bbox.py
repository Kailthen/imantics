
import pytest
from imantics import BBox, Annotation, Category
import pdb

test_shape = [
    # bbox, style, expected shape
    ([0, 0, 10, 15], BBox.XYXY, (10, 15)),
    ([5, 5, 10, 15], BBox.XYXY, (5, 10)),
    ([0, 0, 10, 15], BBox.XYWH, (10, 15)),
    ([5, 5, 10, 15], BBox.XYWH, (10, 15))
]

test_points = [
    # bbox, style, expected min point, expected max point
    ([0, 0, 10, 15], BBox.XYXY, (0, 0), (10, 15)),
    ([5, 5, 10, 15], BBox.XYXY, (5, 5), (10, 15)),
    ([0, 0, 10, 15], BBox.XYWH, (0, 0), (10, 15)),
    ([5, 5, 10, 15], BBox.XYWH, (5, 5), (15, 20))  
]

test_area = [
    # bbox, style, expected area
    ([0, 0, 10, 15], BBox.XYXY, 150),
    ([5, 5, 10, 15], BBox.XYXY, 50),
    ([0, 0, 10, 15], BBox.XYWH, 150),
    ([5, 5, 10, 15], BBox.XYWH, 150)  
]


class TestBBoxConstants:
    def test_styles(self):
        assert BBox.XYXY == "xyxy"
        assert BBox.XYWH == "xywh"

    def test_default_bbox_style(self):
        sut = BBox([0, 0, 0, 0])
        assert sut.style == BBox.XYXY


class TestBBoxMeasurements:

    @pytest.mark.parametrize("bbox,style,e_shape", test_shape)
    def test_shape1(self, bbox, style, e_shape):
        sut = BBox(bbox, style=style)

        assert sut.size == e_shape
        assert sut.width == e_shape[0]
        assert sut.height == e_shape[1]
    
    @pytest.mark.parametrize("bbox,style,e_min,e_max", test_points)
    def test_points1(self, bbox, style, e_min, e_max):
        sut = BBox(bbox, style=style)

        assert sut.min_point == e_min
        assert sut.max_point == e_max
    
    @pytest.mark.parametrize("bbox,style,e_area", test_area)
    def test_area1(self, bbox, style, e_area):
        sut = BBox(bbox, style=style)

        assert sut.area() == e_area

    def test_segmentation(self):
        pass
    
    @pytest.mark.parametrize("bbox,style,e_area", test_area)
    def test_pgl(self, bbox, style, e_area):
        sut = BBox(bbox, style=style)
        score = 0.5
        anno = Annotation(bbox=sut, score=score, category=Category(name="Car"))
        rtn = anno.pgl()
        # pdb.set_trace()
        print(rtn)
        assert rtn['object_data']['bbox'][0]['attributes']['num'][0]['val'] == score


class TestBBoxStyle:
    
    def test_style_change(self):
        pass

