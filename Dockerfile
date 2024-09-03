FROM node:18-alpine
WORKDIR /unleash
COPY index.ts .
COPY tsconfig.json . 
COPY package*.json .
RUN npm install
RUN npm run build

ENTRYPOINT ["npm", "start"]

