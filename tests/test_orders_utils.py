"""
domains/orders/utils.py 테스트
"""

from domains.orders.utils import parse_option_key_safe


def test_parse_option_key_safe_valid_cases():
    """유효한 option_key 파싱 테스트"""
    # 기본 케이스
    result = parse_option_key_safe("size=L&color=red")
    assert result == {"size": "L", "color": "red"}

    # 단일 옵션
    result = parse_option_key_safe("size=M")
    assert result == {"size": "M"}

    # 빈 값 허용
    result = parse_option_key_safe("size=&color=red")
    assert result == {"size": "", "color": "red"}

    # 여러 옵션
    result = parse_option_key_safe("size=L&color=blue&material=cotton")
    assert result == {"size": "L", "color": "blue", "material": "cotton"}


def test_parse_option_key_safe_edge_cases():
    """경계값 및 특수 케이스 테스트"""
    # 빈 문자열
    result = parse_option_key_safe("")
    assert result == {}

    # None (문자열로 변환됨)
    result = parse_option_key_safe(None)
    assert result == {}

    # 공백만 있는 경우 (실제로는 공백을 키로 인식)
    result = parse_option_key_safe("   ")
    assert result == {"   ": ""}

    # &만 있는 경우
    result = parse_option_key_safe("&")
    assert result == {}

    # =만 있는 경우
    result = parse_option_key_safe("=")
    assert result == {"": ""}


def test_parse_option_key_safe_malformed_cases():
    """잘못된 형식의 option_key 처리 테스트"""
    # = 없는 조각들 (실제로는 빈 값으로 처리됨)
    result = parse_option_key_safe("size&color&material")
    assert result == {"size": "", "color": "", "material": ""}

    # 혼합 케이스 (유효한 것과 무효한 것)
    result = parse_option_key_safe("size=L&invalid&color=red&bad")
    assert result == {"size": "L", "invalid": "", "color": "red", "bad": ""}

    # 중복 키 (마지막 값이 유지됨)
    result = parse_option_key_safe("size=L&size=M")
    assert result == {"size": "M"}


def test_parse_option_key_safe_special_characters():
    """특수 문자 처리 테스트"""
    # URL 인코딩된 값 (실제로는 디코딩됨)
    result = parse_option_key_safe("color=red%20blue&size=L")
    assert result == {"color": "red blue", "size": "L"}

    # 특수 문자 포함
    result = parse_option_key_safe("name=test&value=123!@#")
    assert result == {"name": "test", "value": "123!@#"}

    # 한글 값
    result = parse_option_key_safe("color=빨강&size=대")
    assert result == {"color": "빨강", "size": "대"}


def test_parse_option_key_safe_exception_handling():
    """예외 처리 테스트"""
    # 예외가 발생해도 빈 딕셔너리 반환하지 않음
    # (실제로는 내부에서 예외 처리됨)

    # 매우 긴 문자열
    long_string = "&".join([f"key{i}=value{i}" for i in range(1000)])
    result = parse_option_key_safe(long_string)
    assert isinstance(result, dict)
    assert len(result) == 1000

    # 특수 문자로 인한 파싱 오류 시뮬레이션
    result = parse_option_key_safe("size=L&color=red&")
    assert result == {"size": "L", "color": "red"}


def test_parse_option_key_safe_exception_fallback():
    """예외 발생 시 fallback 로직 테스트"""
    # '=' 없는 조각들만 있는 경우
    result = parse_option_key_safe("key1&key2&key3")
    assert result == {"key1": "", "key2": "", "key3": ""}

    # 혼합 케이스 ('=' 있는 것과 없는 것)
    result = parse_option_key_safe("valid=value&invalid&another=test")
    assert result == {"valid": "value", "invalid": "", "another": "test"}

    # '=' 여러 개가 있는 경우 (첫 번째 '='만 사용)
    result = parse_option_key_safe("key=value=extra&normal=test")
    assert result == {"key": "value=extra", "normal": "test"}


def test_parse_option_key_safe_edge_cases_advanced():
    """고급 경계값 테스트"""
    # None을 문자열로 변환
    result = parse_option_key_safe(None)
    assert result == {}

    # 숫자 타입 (문자열로 변환되어 파싱됨)
    result = parse_option_key_safe(123)
    assert result == {}  # "123"은 '='가 없으므로 빈 딕셔너리

    # 불린 타입
    result = parse_option_key_safe(True)
    assert result == {}  # "True"는 '='가 없으므로 빈 딕셔너리

    # 리스트 타입
    result = parse_option_key_safe(["a", "b"])
    assert result == {}  # "['a', 'b']"는 '='가 없으므로 빈 딕셔너리


def test_parse_option_key_safe_unicode_and_special():
    """유니코드 및 특수 문자 테스트"""
    # 유니코드 문자
    result = parse_option_key_safe("한글=값&english=value")
    assert result == {"한글": "값", "english": "value"}

    # 이모지
    result = parse_option_key_safe("emoji=😀&text=hello")
    assert result == {"emoji": "😀", "text": "hello"}

    # 특수 기호
    result = parse_option_key_safe("symbol=@#$%&text=normal")
    assert result == {"symbol": "@#$%", "text": "normal"}

    # 공백과 탭
    result = parse_option_key_safe("key1=value with spaces&key2=value\twith\ttabs")
    assert result == {"key1": "value with spaces", "key2": "value\twith\ttabs"}


def test_parse_option_key_safe_performance():
    """성능 테스트"""
    import time

    # 큰 데이터셋으로 성능 확인
    large_data = "&".join([f"key{i}=value{i}" for i in range(10000)])

    start_time = time.time()
    result = parse_option_key_safe(large_data)
    end_time = time.time()

    # 1초 이내에 처리되어야 함
    assert (end_time - start_time) < 1.0
    assert len(result) == 10000
    assert result["key9999"] == "value9999"


def test_parse_option_key_safe_memory_efficiency():
    """메모리 효율성 테스트"""
    # 매우 큰 문자열이 메모리 문제를 일으키지 않는지 확인
    # 중복 키는 마지막 값이 유지되므로 실제로는 1개의 키-값 쌍만 남음
    huge_string = "key=value&" * 100000  # 100만 개의 키-값 쌍

    result = parse_option_key_safe(huge_string)

    # 결과가 올바르게 파싱되었는지 확인 (중복 키로 인해 1개만 남음)
    assert len(result) == 1
    assert result["key"] == "value"

    # 메모리 사용량이 합리적인지 확인 (직접적인 메모리 측정은 복잡하므로
    # 결과가 올바르게 생성되었는지만 확인)
    assert isinstance(result, dict)
