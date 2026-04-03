FROM node:20-alpine
WORKDIR /app

# Install dependencies
COPY job-hunter-dashboard/package*.json ./
RUN npm install

# Copy all source code
COPY job-hunter-dashboard/ .

# Run the build (Vite creates the 'dist' folder)
RUN npm run build

# Install a simple static server to serve the 'dist' folder
RUN npm install -g serve

ENV NODE_ENV=production
EXPOSE 3000

# Start the application using 'serve' on port 3000
CMD ["npx", "serve", "-s", "dist", "-l", "3000"]
