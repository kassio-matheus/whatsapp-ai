# Monorepo

Aplicação com frontend Next.js e backend FastAPI, organizada com Bun e Turborepo.

## Deploy no Railway

O projeto deve ser publicado como dois serviços dentro do mesmo projeto Railway:

- `frontend`: serviço Next.js, usando a raiz `/` do repositório. Ele precisa da raiz porque importa o pacote compartilhado `@workspace/ui`.
- `backend`: serviço FastAPI, usando `/apps/backend` como Root Directory.

Os arquivos de configuração já estão em `apps/frontend/railway.json` e
`apps/backend/railway.json`. O backend também possui `apps/backend/railpack.json`
para incluir a biblioteca nativa `libpq5` no runtime. Ao usar a importação automática de monorepo do
Railway, eles são detectados por pacote. Se configurar os serviços manualmente,
defina os Config Files como `/apps/frontend/railway.json` e
`/apps/backend/railway.json`, respectivamente.

### Variáveis do backend

Adicione no serviço `backend`:

```text
ENVIRONMENT=production
SECRET_KEY=<uma-chave-aleatória-com-pelo-menos-32-caracteres>
SQLALCHEMY_DATABASE_URI=${{Postgres.DATABASE_URL}}
BACKEND_CORS_ORIGINS=["https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}"]
ALLOWED_HOSTS=["${{RAILWAY_PUBLIC_DOMAIN}}","healthcheck.railway.app"]
FRONTEND_HOST=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
# Alternativa caso o Railpack não detecte automaticamente o railpack.json:
# RAILPACK_DEPLOY_APT_PACKAGES=libpq5
```

Troque `Postgres` e `frontend` pelos nomes exatos dos serviços no seu projeto.
Configure também `OPENAI_API_KEY` e as variáveis SMTP se esses recursos forem
usados. O `preDeployCommand` executa as migrações do Alembic antes de ativar o
novo deploy.

### Variáveis do frontend

Adicione no serviço `frontend`:

```text
NEXT_PUBLIC_API_URL=https://${{backend.RAILWAY_PUBLIC_DOMAIN}}/api/v1
```

Como `NEXT_PUBLIC_*` é incorporada ao bundle durante o build do Next.js, faça um
novo deploy do frontend quando essa URL mudar.

### Ordem recomendada

1. Crie um serviço Postgres no projeto Railway.
2. Crie os serviços `backend` e `frontend`, configure os Root Directories e os
   Config Files indicados acima.
3. Gere os domínios públicos dos dois serviços e configure as variáveis usando
   as referências Railway acima.
4. Faça o deploy do `backend` e depois do `frontend`.

Os healthchecks configurados são `/api/v1/health` no backend e `/health` no
frontend. Ambos retornam HTTP 200 sem depender de autenticação.

O diretório de uploads do backend é armazenamento efêmero por padrão. Se os
uploads precisarem sobreviver a novos deploys, anexe um Railway Volume no
serviço e defina `UPLOAD_DIR` para o caminho montado.

## Adding components

To add components to your app, run the following command at the root of your `web` app:

```bash
pnpm dlx shadcn@latest add button -c apps/web
```

This will place the ui components in the `packages/ui/src/components` directory.

## Using components

To use the components in your app, import them from the `ui` package.

```tsx
import { Button } from "@workspace/ui/components/button";
```
