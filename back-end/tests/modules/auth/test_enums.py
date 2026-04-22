from app.modules.auth.enums import EducationLevel


def test_education_level_has_six_values() -> None:
    assert len(EducationLevel) == 6


def test_education_level_values_match_flutter_form() -> None:
    assert EducationLevel.ENSINO_FUNDAMENTAL.value == "Ensino Fundamental"
    assert EducationLevel.ENSINO_MEDIO.value == "Ensino Médio"
    assert EducationLevel.ENSINO_SUPERIOR.value == "Ensino Superior"
    assert EducationLevel.POS_GRADUACAO.value == "Pós-graduação"
    assert EducationLevel.MESTRADO.value == "Mestrado"
    assert EducationLevel.DOUTORADO.value == "Doutorado"


def test_education_level_is_str_enum() -> None:
    assert isinstance(EducationLevel.MESTRADO, str)
    assert EducationLevel.MESTRADO == "Mestrado"
