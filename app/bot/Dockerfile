FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod ./
COPY go.sum ./
RUN go mod download

COPY . .

RUN go build -o bot ./cmd/bot

FROM alpine:3.19

WORKDIR /app

COPY --from=builder /app/bot .

ENV API_BASE_URL=http://api:8000

CMD ["./bot"]


