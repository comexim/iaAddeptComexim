from app.services.stock_metrics import (
    certificate_matches,
    detect_certificate_from_query,
    normalize_certificate,
)


def test_certificate_filter_uses_exact_normalized_match():
    assert certificate_matches("RF", "RF")
    assert certificate_matches(" RF ", "RF")

    assert not certificate_matches("Rainforest", "RF")
    assert not certificate_matches("4C", "RF")
    assert not certificate_matches("GCP", "GC")
    assert not certificate_matches("FT", "RF")
    assert not certificate_matches("RFA", "RF")


def test_certificate_detection_from_query():
    assert detect_certificate_from_query("Quanto estoque RF temos?") == "RF"
    assert detect_certificate_from_query("Café Rainforest em estoque") == "RF"
    assert detect_certificate_from_query("Separe estoque 4 C") == "4C"
    assert detect_certificate_from_query("Quanto estoque GCP temos?") == "GCP"


def test_certificate_normalization():
    assert normalize_certificate(" rf ") == "RF"
    assert normalize_certificate("4 c") == "4C"
    assert normalize_certificate("Rainforest") == "RAINFOREST"
    assert normalize_certificate("") == "SEM CERTIFICADO"


if __name__ == "__main__":
    test_certificate_filter_uses_exact_normalized_match()
    test_certificate_detection_from_query()
    test_certificate_normalization()
    print("stock_metrics: OK")
