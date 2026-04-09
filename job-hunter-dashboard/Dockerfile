FROM node:20-alpine
WORKDIR /app

# Accept the API URL as a build argument
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

COPY package*.json ./
RUN npm install

COPY . .

# Now the build process will "see" the VITE_API_URL
RUN npm run build

RUN npm install -g serve
ENV NODE_ENV=production
EXPOSE 3000

CMD ["npx", "serve", "-s", "dist", "-l", "3000"]
