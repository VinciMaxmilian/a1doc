"""Cookies de sessão.

Por que cookie e não `localStorage`: o token em `localStorage` é legível por
qualquer JavaScript que rode na página, então um único XSS entrega a sessão.
Um cookie `HttpOnly` não é acessível por script.

O preço de usar cookie é CSRF — o navegador envia o cookie sozinho, inclusive
numa requisição disparada por outro site. Daí o `SameSite` e o token CSRF em
double-submit (ver `csrf.py`).

Três cookies:

- `indoc_access`  — HttpOnly, curto. Autentica a requisição.
- `indoc_refresh` — HttpOnly, longo, com `path` restrito às rotas que o usam.
- `indoc_csrf`    — **não** HttpOnly: o front precisa ler para reenviar no
                    header. Não é segredo de autenticação; só prova que quem
                    montou a requisição consegue ler o domínio.
"""
import config

# O refresh só é enviado para as rotas que o consomem. Assim ele não acompanha
# toda requisição da API, reduzindo a superfície de exposição.
PATH_REFRESH = "/auth"


def _base(max_age: int | None = None) -> dict:
    opcoes = {
        "httponly": True,
        "secure": config.COOKIE_SECURE,
        "samesite": config.COOKIE_SAMESITE,
        "domain": config.COOKIE_DOMAIN,
    }
    if max_age is not None:
        opcoes["max_age"] = max_age
    return opcoes


def definir_sessao(response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    response.set_cookie(
        config.COOKIE_ACCESS, access_token, path="/",
        **_base(max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
    )
    response.set_cookie(
        config.COOKIE_REFRESH, refresh_token, path=PATH_REFRESH,
        **_base(max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600),
    )
    # Legível por JS de propósito — é metade do double-submit.
    response.set_cookie(
        config.COOKIE_CSRF, csrf_token, path="/",
        httponly=False,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        domain=config.COOKIE_DOMAIN,
        max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )


def limpar_sessao(response) -> None:
    """Apaga os três cookies. `path` precisa bater com o do set_cookie."""
    response.delete_cookie(config.COOKIE_ACCESS, path="/", domain=config.COOKIE_DOMAIN)
    response.delete_cookie(config.COOKIE_REFRESH, path=PATH_REFRESH, domain=config.COOKIE_DOMAIN)
    response.delete_cookie(config.COOKIE_CSRF, path="/", domain=config.COOKIE_DOMAIN)
