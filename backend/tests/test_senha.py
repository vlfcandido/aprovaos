# O que é: testes do passo 9 da V1 — hash argon2id e verificação de senha, sem I/O.
# Quando ler: ao mudar parâmetros do hasher ou a política de tratamento de hash inválido.
from aprovaos.dominio.senha import gerar_hash, verificar


def test_gerar_hash_e_argon2id() -> None:
    hash_ = gerar_hash("segredo123")
    assert hash_.startswith("$argon2id$")
    assert hash_ != "segredo123"


def test_dois_hashes_diferem() -> None:
    assert gerar_hash("segredo123") != gerar_hash("segredo123")


def test_verificar() -> None:
    hash_ = gerar_hash("segredo123")
    assert verificar(hash_, "segredo123") is True
    assert verificar(hash_, "outra") is False
    assert verificar("lixo", "x") is False
    # Hash com formato argon2 mas conteúdo inválido também não estoura.
    assert verificar("$argon2id$v=19$m=65536,t=3,p=4$abc$def", "x") is False
