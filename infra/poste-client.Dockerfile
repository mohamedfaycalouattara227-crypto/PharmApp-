# infra/poste-client.Dockerfile — Poste client PharmApp (mode développement/recette).
# Le contexte de build est la RACINE du dépôt : le fichier VERSION doit être
# accessible pour que la version injectée soit celle du dépôt (règle G-02).

FROM node:20-alpine

WORKDIR /app

COPY VERSION /VERSION
COPY apps/poste-client/package.json apps/poste-client/package-lock.json ./
RUN npm ci

COPY apps/poste-client/ ./
COPY VERSION /app/../VERSION

ENV PORT=3000
EXPOSE 3000

CMD ["npm", "run", "dev"]
