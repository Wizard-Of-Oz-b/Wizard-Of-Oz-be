import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from domains.catalog.services import (
    OutOfStockError,
    StockRowMissing,
    normalize_option_key,
    reserve_stock,
    release_stock,
    get_stock_quantity,
)
from domains.catalog.models import Product, ProductStock, Category
from domains.accounts.models import User


class TestNormalizeOptionKey:
    """normalize_option_key 함수 테스트"""
    
    def test_normalize_option_key_dict(self):
        """딕셔너리 옵션 키 정규화 테스트"""
        # 기본 딕셔너리
        result = normalize_option_key({"size": "L", "color": "red"})
        assert result == "color=red&size=L"  # 키 정렬됨
        
        # 리스트/튜플 값
        result = normalize_option_key({"sizes": ["S", "M", "L"], "colors": ("red", "blue")})
        assert "sizes=S%2CM%2CL" in result  # URL 인코딩됨
        assert "colors=red%2Cblue" in result
        
        # None 값
        result = normalize_option_key({"size": "L", "color": None})
        assert result == "color=&size=L"
        
        # 빈 딕셔너리
        result = normalize_option_key({})
        assert result == ""
    
    def test_normalize_option_key_string(self):
        """문자열 옵션 키 정규화 테스트"""
        # 기본 쿼리 스트링
        result = normalize_option_key("size=L&color=red")
        assert result == "color=red&size=L"  # 정렬됨
        
        # 빈 값 포함
        result = normalize_option_key("size=&color=red")
        assert result == "color=red&size="
        
        # 빈 문자열
        result = normalize_option_key("")
        assert result == ""
        
        # 잘못된 형식
        result = normalize_option_key("invalid")
        assert result == "invalid="
    
    def test_normalize_option_key_edge_cases(self):
        """경계값 테스트"""
        # None
        result = normalize_option_key(None)
        assert result == ""
        
        # 숫자
        result = normalize_option_key(123)
        assert result == "123"
        
        # 불린
        result = normalize_option_key(True)
        assert result == "True"


@pytest.mark.django_db
class TestReserveStock:
    """reserve_stock 함수 테스트"""
    
    def test_reserve_stock_success(self, product_factory):
        """재고 예약 성공 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 재고 생성
        stock = ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=10
        )
        
        # 재고 예약
        reserve_stock(product.id, option_key, 5)
        
        # 재고 확인
        stock.refresh_from_db()
        assert stock.stock_quantity == 5  # 10 - 5 = 5
    
    def test_reserve_stock_insufficient(self, product_factory):
        """재고 부족 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 재고 생성 (부족한 수량)
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=3
        )
        
        # 재고 부족 에러
        with pytest.raises(OutOfStockError, match="재고 부족"):
            reserve_stock(product.id, option_key, 5)
    
    def test_reserve_stock_create_missing_row(self, product_factory):
        """존재하지 않는 재고 행 생성 테스트"""
        product = product_factory()
        option_key = {"size": "M"}
        
        # 재고 행이 없는 상태에서 예약 시도
        with pytest.raises(OutOfStockError, match="재고 부족"):
            reserve_stock(product.id, option_key, 1)
        
        # 트랜잭션 롤백으로 인해 재고 행이 생성되지 않음
        # (예외 발생 시 트랜잭션이 롤백되므로)
        assert not ProductStock.objects.filter(product=product, option_key="size=M").exists()
    
    def test_reserve_stock_zero_quantity(self, product_factory):
        """0 수량 예약 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 0 수량은 무시됨
        reserve_stock(product.id, option_key, 0)
        
        # 재고 행이 생성되지 않았는지 확인
        assert not ProductStock.objects.filter(product=product, option_key="size=L").exists()
    
    def test_reserve_stock_negative_quantity(self, product_factory):
        """음수 수량 예약 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 음수 수량은 무시됨
        reserve_stock(product.id, option_key, -1)
        
        # 재고 행이 생성되지 않았는지 확인
        assert not ProductStock.objects.filter(product=product, option_key="size=L").exists()
    
    def test_reserve_stock_string_option_key(self, product_factory):
        """문자열 옵션 키로 재고 예약 테스트"""
        product = product_factory()
        option_key_str = "size=L&color=red"
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="color=red&size=L",  # 정규화된 형태
            stock_quantity=10
        )
        
        # 재고 예약
        reserve_stock(product.id, option_key_str, 3)
        
        # 재고 확인
        stock = ProductStock.objects.get(product=product, option_key="color=red&size=L")
        assert stock.stock_quantity == 7


@pytest.mark.django_db
class TestReleaseStock:
    """release_stock 함수 테스트"""
    
    def test_release_stock_success(self, product_factory):
        """재고 복구 성공 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 재고 생성
        stock = ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=5
        )
        
        # 재고 복구
        release_stock(product.id, option_key, 3)
        
        # 재고 확인
        stock.refresh_from_db()
        assert stock.stock_quantity == 8  # 5 + 3 = 8
    
    def test_release_stock_create_missing_row(self, product_factory):
        """존재하지 않는 재고 행 생성 후 복구 테스트"""
        product = product_factory()
        option_key = {"size": "M"}
        
        # 재고 행이 없는 상태에서 복구
        release_stock(product.id, option_key, 5)
        
        # 재고 행이 생성되었는지 확인
        stock = ProductStock.objects.get(product=product, option_key="size=M")
        assert stock.stock_quantity == 5
    
    def test_release_stock_zero_quantity(self, product_factory):
        """0 수량 복구 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 0 수량은 무시됨
        release_stock(product.id, option_key, 0)
        
        # 재고 행이 생성되지 않았는지 확인
        assert not ProductStock.objects.filter(product=product, option_key="size=L").exists()
    
    def test_release_stock_negative_quantity(self, product_factory):
        """음수 수량 복구 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 음수 수량은 무시됨
        release_stock(product.id, option_key, -1)
        
        # 재고 행이 생성되지 않았는지 확인
        assert not ProductStock.objects.filter(product=product, option_key="size=L").exists()


@pytest.mark.django_db
class TestGetStockQuantity:
    """get_stock_quantity 함수 테스트"""
    
    def test_get_stock_quantity_existing(self, product_factory):
        """기존 재고 수량 조회 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=15
        )
        
        # 재고 수량 조회
        quantity = get_stock_quantity(product.id, option_key)
        assert quantity == 15
    
    def test_get_stock_quantity_missing(self, product_factory):
        """존재하지 않는 재고 수량 조회 테스트"""
        product = product_factory()
        option_key = {"size": "M"}
        
        # 재고 수량 조회 (존재하지 않음)
        quantity = get_stock_quantity(product.id, option_key)
        assert quantity == 0
    
    def test_get_stock_quantity_string_option_key(self, product_factory):
        """문자열 옵션 키로 재고 수량 조회 테스트"""
        product = product_factory()
        option_key_str = "size=L&color=red"
        
        # 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="color=red&size=L",  # 정규화된 형태
            stock_quantity=20
        )
        
        # 재고 수량 조회
        quantity = get_stock_quantity(product.id, option_key_str)
        assert quantity == 20


@pytest.mark.django_db
class TestStockIntegration:
    """재고 관련 통합 테스트"""
    
    def test_reserve_and_release_cycle(self, product_factory):
        """재고 예약과 복구 사이클 테스트"""
        product = product_factory()
        option_key = {"size": "L"}
        
        # 초기 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=10
        )
        
        # 재고 예약
        reserve_stock(product.id, option_key, 3)
        assert get_stock_quantity(product.id, option_key) == 7
        
        # 재고 복구
        release_stock(product.id, option_key, 2)
        assert get_stock_quantity(product.id, option_key) == 9
        
        # 다시 예약
        reserve_stock(product.id, option_key, 1)
        assert get_stock_quantity(product.id, option_key) == 8
    
    def test_multiple_option_keys(self, product_factory):
        """여러 옵션 키에 대한 재고 관리 테스트"""
        product = product_factory()
        
        # 여러 옵션의 재고 생성
        ProductStock.objects.create(
            product=product,
            option_key="size=S",
            stock_quantity=5
        )
        ProductStock.objects.create(
            product=product,
            option_key="size=M",
            stock_quantity=10
        )
        ProductStock.objects.create(
            product=product,
            option_key="size=L",
            stock_quantity=15
        )
        
        # 각각 다른 수량으로 예약
        reserve_stock(product.id, {"size": "S"}, 2)
        reserve_stock(product.id, {"size": "M"}, 5)
        reserve_stock(product.id, {"size": "L"}, 3)
        
        # 각각의 재고 확인
        assert get_stock_quantity(product.id, {"size": "S"}) == 3
        assert get_stock_quantity(product.id, {"size": "M"}) == 5
        assert get_stock_quantity(product.id, {"size": "L"}) == 12


@pytest.mark.django_db
class TestNormalizeOptionKeyEdgeCases:
    """normalize_option_key 함수의 추가 엣지 케이스 테스트"""

    def test_normalize_option_key_string_empty_pairs(self):
        """빈 pairs가 반환되는 경우 테스트 (51번째 줄 커버)"""
        # parse_qsl이 빈 결과를 반환하는 경우를 시뮬레이션
        # 실제로는 이런 경우가 발생하기 어렵지만, 코드 커버리지를 위해 테스트
        assert normalize_option_key("") == ""  # 빈 문자열
        # 공백만 있는 경우는 실제로 공백을 키로 인식하므로 URL 인코딩됨
        assert normalize_option_key("   ") == "+++="  # 공백이 URL 인코딩됨
        
        # 실제로 51번째 줄을 커버하려면 다른 방법이 필요
        # parse_qsl이 빈 결과를 반환하는 특수한 경우를 만들어보자
        # 하지만 실제로는 parse_qsl이 대부분의 경우 결과를 반환하므로
        # 이 테스트는 현재 구현에서는 51번째 줄을 커버하기 어려움

    def test_normalize_option_key_string_empty_pairs_with_mock(self):
        """mock을 사용하여 51번째 줄 커버 테스트"""
        from unittest.mock import patch
        
        # parse_qsl이 빈 결과를 반환하도록 mock
        with patch('domains.catalog.services.parse_qsl', return_value=[]):
            result = normalize_option_key("test=value")
            assert result == ""  # 51번째 줄이 실행됨
