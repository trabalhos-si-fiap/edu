"""Fixa o formato de barramento de cada evento.

Todo nome de chave e toda routing key aparecem aqui como **literal**, nunca
como `DiagnosticCompleted.ROUTING_KEY` ou similar: importar a constante da
própria implementação faria este teste acompanhar uma renomeação em vez de
detectá-la, que é exatamente o buraco que `contracts.py` existe para fechar.
"""

from edu_common.contracts import DiagnosticCompleted, StudentCreated


def test_diagnostic_completed_routing_key_is_stable():
    assert DiagnosticCompleted.ROUTING_KEY == "diagnostic.completed"


def test_diagnostic_completed_payload_keys_are_the_wire_format():
    payload = DiagnosticCompleted(
        aluno_id="00000000-0000-0000-0000-000000000001",
        tema_id=12,
        dominio_tema=0.85,
        acao="avancar",
    ).to_payload()

    assert payload == {
        "aluno_id": "00000000-0000-0000-0000-000000000001",
        "tema_id": 12,
        "dominio_tema": 0.85,
        "acao": "avancar",
    }


def test_student_created_routing_key_is_stable():
    assert StudentCreated.ROUTING_KEY == "student.created"


def test_student_created_payload_keys_are_the_wire_format():
    payload = StudentCreated(
        aluno_id="00000000-0000-0000-0000-000000000001",
        nome="Ana",
        email="ana@example.com",
    ).to_payload()

    assert payload == {
        "aluno_id": "00000000-0000-0000-0000-000000000001",
        "nome": "Ana",
        "email": "ana@example.com",
    }
