# Orçai

Sistema de controle financeiro pessoal (Django + templates + Tailwind via CDN).

## Requisitos

- Python 3.11+ (testado com 3.13)
- Ambiente virtual recomendado

## Como rodar

```powershell
cd "caminho\para\Orçai"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Abra `http://127.0.0.1:8000/`. Use o usuário de demonstração:

- **E-mail:** `demo@orcai.local`
- **Senha:** `demo12345` (ou o valor passado em `--password` no `seed_demo`)

Para administrar o banco: `http://127.0.0.1:8000/admin/` (crie um superusuário com `python manage.py createsuperuser`).

## Estrutura de apps

| App         | Função                                              |
|------------|------------------------------------------------------|
| `users`    | Modelo de usuário customizado, perfil, cadastro      |
| `finance`  | Categorias, transações, parcelas, contas fixas, notificações |
| `dashboard`| Painel (será expandido nas próximas etapas)         |

## Dados de exemplo

```powershell
python manage.py seed_demo --password minhasenha
```

## Recuperação de senha

Em desenvolvimento, o e-mail é impresso no console do `runserver` (backend `console.EmailBackend`).
