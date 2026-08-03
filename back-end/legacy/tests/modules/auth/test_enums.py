from app.modules.auth.enums import EducationLevel


def test_education_level_has_five_values() -> None:
    assert len(EducationLevel) == 5


def test_education_level_values_match_flutter_form() -> None:
    assert EducationLevel.NONO_ANO.value == "9º ano"
    assert EducationLevel.PRIMEIRO_ANO.value == "1º ano"
    assert EducationLevel.SEGUNDO_ANO.value == "2º ano"
    assert EducationLevel.TERCEIRO_ANO.value == "3º ano"
    assert EducationLevel.VESTIBULANDO.value == "Vestibulando"


def test_education_level_is_str_enum() -> None:
    assert isinstance(EducationLevel.VESTIBULANDO, str)
    assert EducationLevel.VESTIBULANDO == "Vestibulando"
