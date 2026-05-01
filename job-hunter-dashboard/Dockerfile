FROM node:20-alpine
WORKDIR /app

ARG VITE_API_URL=http://localhost:8000/api/v1
ENV VITE_API_URL=$VITE_API_URL

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

RUN npm install -g serve
ENV NODE_ENV=production
EXPOSE 5173

CMD ["npx", "serve", "-s", "dist", "-l", "5173"]
