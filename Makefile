# Makefile — Ariadne Runtime
#
# Este arquivo cobre apenas construção e verificação do código.
# Para executar cenários, campanhas, status e visualizadores, use ./ariadne.

PROTO_DIR      := proto
GO_OUT_DIR     := runtime/gen/go
PYTHON_OUT_DIR := sdk/python/src
PROTO_INCLUDES ?= $(shell pkg-config --variable=includedir protobuf 2>/dev/null || echo /usr/include)

PROTO_FILES    := $(shell find $(PROTO_DIR) -name "*.proto")

# check-env — pré-requisito interno de `proto`: confere as ferramentas de geração

.PHONY: check-env
check-env:
	@echo "Verificando ferramentas de geração..."
	@which go > /dev/null 2>&1 || (echo "ERRO: go nao encontrado" && exit 1)
	@which protoc > /dev/null 2>&1 || (echo "ERRO: protoc nao encontrado" && exit 1)
	@PATH="$(PATH):$$(go env GOPATH)/bin" command -v protoc-gen-go > /dev/null 2>&1 || (echo "ERRO: protoc-gen-go nao encontrado. Rode: go install google.golang.org/protobuf/cmd/protoc-gen-go@latest" && exit 1)
	@PATH="$(PATH):$$(go env GOPATH)/bin" command -v protoc-gen-go-grpc > /dev/null 2>&1 || (echo "ERRO: protoc-gen-go-grpc nao encontrado. Rode: go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest" && exit 1)
	@which uv > /dev/null 2>&1 || (echo "ERRO: uv nao encontrado. Rode: brew install uv" && exit 1)
	@echo "Tudo ok."

# proto — gera stubs Go e Python a partir dos .proto

.PHONY: proto
proto: check-env
	@echo "Criando diretorios de saida..."
	@mkdir -p $(GO_OUT_DIR)
	@mkdir -p $(PYTHON_OUT_DIR)
	@echo "Gerando stubs Go..."
	PATH="$(PATH):$$(go env GOPATH)/bin" protoc \
		--proto_path=$(PROTO_DIR) \
		--proto_path=$(PROTO_INCLUDES) \
		--go_out=$(GO_OUT_DIR) \
		--go_opt=paths=source_relative \
		--go-grpc_out=$(GO_OUT_DIR) \
		--go-grpc_opt=paths=source_relative \
		$(PROTO_FILES)
	@echo "Gerando stubs Python..."
	uv run --directory sdk/python python3 -m grpc_tools.protoc \
		--proto_path=$(CURDIR)/$(PROTO_DIR) \
		--python_out=$(CURDIR)/$(PYTHON_OUT_DIR) \
		--grpc_python_out=$(CURDIR)/$(PYTHON_OUT_DIR) \
		$(CURDIR)/$(PROTO_FILES)
	@echo "Proto gerado com sucesso."

# contract-check — detecta alterações não versionadas no contrato congelado

.PHONY: contract-check
contract-check:
	@sh tools/check-contract-freeze.sh

# build — compila os servicos Go

.PHONY: build
build:
	@echo "Compilando servicos Go..."
	cd runtime && go build ./...

# verify — verificação integrada sem chamadas LLM (mesma rotina do CI)

.PHONY: verify
verify:
	uv run --locked --project sdk/python --extra llm python tools/verify.py

# test-go — apenas os testes Go, isolados

.PHONY: test-go
test-go:
	cd runtime && go test ./...

# help — lista os targets

.PHONY: help
help:
	@echo ""
	@echo "Construcao e verificacao:"
	@echo "  make proto           Gera stubs Go e Python a partir dos .proto"
	@echo "  make contract-check  Confere o contrato congelado"
	@echo "  make build           Compila os servicos Go"
	@echo "  make verify          Verifica contrato, Go, SDK, estudos e ferramentas"
	@echo "  make test-go         Executa somente os testes Go"
	@echo ""
	@echo "Para executar cenarios, campanhas, status, logs e o Mission Viewer: ./ariadne help"
	@echo ""
