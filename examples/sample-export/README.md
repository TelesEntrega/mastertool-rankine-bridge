# Export de exemplo

Um export sintético completo (3 objetos, manifesto e metadados válidos) está em
`tests/fixtures/sample_project/` e é usado pelos testes automatizados.

Para experimentar a CLI com ele:

```bash
mastertool-bridge validate-export tests/fixtures/sample_project
mastertool-bridge inspect tests/fixtures/sample_project
mastertool-bridge find-writes tests/fixtures/sample_project xMotorLigado
```

Nunca coloque exports de projetos reais de clientes em `examples/` ou em
qualquer pasta versionada — use `workspace/exports/` (ignorada pelo Git).
