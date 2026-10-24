
import pytest

from simulation.congestion import CongestionDetector


def test_no_congestion_below_thresholds():
    detector = CongestionDetector(10, 10)
    assert detector.detect(5, 5) is False


def test_congestion_when_demand_exceeds_threshold():
    detector = CongestionDetector(10, 10)
    assert detector.detect(11, 5) is True


def test_congestion_when_queue_exceeds_threshold():
    detector = CongestionDetector(10, 10)
    assert detector.detect(5, 11) is True


def test_congestion_when_both_exceed_thresholds():
    detector = CongestionDetector(10, 10)
    assert detector.detect(11, 11) is True


def test_equal_threshold_does_not_trigger_congestion():
    detector = CongestionDetector(10, 10)
    assert detector.detect(10, 10) is False


def test_thresholds_are_configurable():
    detector = CongestionDetector(
        demand_threshold=20,
        queue_length_threshold=5,
    )
    assert detector.detect(15, 6) is True
    assert detector.detect(15, 5) is False


def test_negative_threshold_is_rejected():
    with pytest.raises(ValueError):
        CongestionDetector(-1, 10)


def test_negative_demand_is_rejected():
    detector = CongestionDetector(10, 10)
    with pytest.raises(ValueError):
        detector.detect(-1, 5)


def test_negative_queue_length_is_rejected():
    detector = CongestionDetector(10, 10)
    with pytest.raises(ValueError):
        detector.detect(5, -1)


def test_non_numeric_demand_is_rejected():
    detector = CongestionDetector(10, 10)
    with pytest.raises(TypeError):
        detector.detect("high", 5)


def test_custom_congestion_rule_requires_both_thresholds():
    from simulation.congestion import BothThresholdsExceeded

    detector = CongestionDetector(
        demand_threshold=10,
        queue_length_threshold=10,
        rule=BothThresholdsExceeded(),
    )

    assert detector.detect(11, 5) is False
    assert detector.detect(5, 11) is False
    assert detector.detect(11, 11) is True


def test_default_congestion_rule_preserves_existing_behavior():
    detector = CongestionDetector(10, 10)

    assert detector.detect(11, 5) is True
    assert detector.detect(5, 11) is True
