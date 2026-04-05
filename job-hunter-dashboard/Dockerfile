FROM node:20-alpine
WORKDIR /app

# 1. Install dependencies
# We use ./ because we are already inside the dashboard context
COPY package*.json ./
RUN npm install

# 2. Copy all source code from the current context
COPY . .

# 3. Run the build (Vite + Tailwind v4)
RUN npm run build

# 4. Install 'serve' for production
RUN npm install -g serve

ENV NODE_ENV=production
EXPOSE 3000

# 5. Start the application
CMD ["npx", "serve", "-s", "dist", "-l", "3000"]
