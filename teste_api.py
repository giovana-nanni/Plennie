
import json
import sys
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:5000"
falhas = []
cookie = None


def chamar(metodo, caminho, corpo=None):
    """Faz a requisição e devolve (status, dict). Levanta em erro de rede."""
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    headers = {"Content-Type": "application/json"} if corpo is not None else {}
    if cookie:
        headers["Cookie"] = cookie
    req = Request(BASE + caminho, data=dados, headers=headers, method=metodo)
    try:
        with urlopen(req) as r:
            set_cookie = r.headers.get("Set-Cookie")
            if set_cookie:
                global cookie
                cookie = set_cookie.split(";")[0]
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except HTTPError as e:
        set_cookie = e.headers.get("Set-Cookie")
        if set_cookie:
            cookie = set_cookie.split(";")[0]
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def checar(nome, condicao, detalhe=""):
    if condicao:
        print(f"  [OK] {nome}")
    else:
        print(f"  [FALHOU] {nome} {detalhe}")
        falhas.append(nome)


def main():
    hoje = date.today().isoformat()
    email = f"teste_{date.today().isoformat()}@plennie.local"
    senha = "senha-teste-123"

    # CT00: registrar (setup)
    print("CT00) POST /api/registrar")
    status, resp = chamar("POST", "/api/registrar",
                          {"email": email, "senha": senha})
    checar("status 201 (ou 409 se já existe)", status in (201, 409),
           f"(recebido {status})")

    # CT03: sem login -> 401
    print("CT03) GET /api/despesas sem login")
    global cookie
    cookie_salvo = cookie
    cookie = None
    status, _ = chamar("GET", "/api/despesas")
    checar("status 401", status == 401, f"(recebido {status})")
    cookie = cookie_salvo

    # login para os próximos testes
    print("CT00b) POST /api/login")
    status, resp = chamar("POST", "/api/login", {"email": email, "senha": senha})
    checar("status 200", status == 200, f"(recebido {status})")

    # CT01: cadastrar despesa válida
    print("CT01) POST /api/despesas (válido)")
    status, resp = chamar("POST", "/api/despesas", {
        "descricao": "Teste de cadastro",
        "valor": 25.50,
        "data": hoje,
        "categoria": "Alimentação",
    })
    checar("status 201", status == 201, f"(recebido {status})")
    checar("id retornado", isinstance(resp.get("id"), int), resp)
    novo_id = resp.get("id")

    # CT02: valor negativo -> 400
    print("CT02) POST /api/despesas (valor negativo)")
    status, _ = chamar("POST", "/api/despesas", {
        "descricao": "Negativo", "valor": -1,
        "data": hoje, "categoria": "X",
    })
    checar("status 400", status == 400, f"(recebido {status})")

    # CT04: usuário B não vê despesa do usuário A
    print("CT04) isolamento entre usuários")
    cookie_a = cookie
    email_b = f"teste_b_{date.today().isoformat()}@plennie.local"
    chamar("POST", "/api/registrar", {"email": email_b, "senha": senha})
    status, resp = chamar("GET", f"/api/despesas/{novo_id}")
    checar("status 404 (não vê do outro)", status == 404,
           f"(recebido {status})")
    cookie = cookie_a

    # CT05: rate limit de login (5 tentativas erradas -> 429)
    print("CT05) rate limit de login")
    cookie_b = cookie
    cookie = None
    for _ in range(5):
        chamar("POST", "/api/login", {"email": email_b, "senha": "errada"})
    status, _ = chamar("POST", "/api/login", {"email": email_b, "senha": "errada"})
    checar("status 429", status == 429, f"(recebido {status})")
    cookie = cookie_b

    # DELETE e 404
    if novo_id is not None:
        print("CT06) DELETE /api/despesas/<id>")
        status, _ = chamar("DELETE", f"/api/despesas/{novo_id}")
        checar("status 200", status == 200, f"(recebido {status})")
        status, _ = chamar("DELETE", "/api/despesas/99999999")
        checar("404 em id inexistente", status == 404, f"(recebido {status})")

    print()
    if falhas:
        print(f"[FALHOU] {len(falhas)} falha(s): {falhas}")
        return 1
    print("[OK] Todos os testes passaram.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except URLError as e:
        print(f"[ERRO] Não foi possível conectar em {BASE}: {e}")
        print("   O servidor está rodando? (python app.py)")
        sys.exit(1)
