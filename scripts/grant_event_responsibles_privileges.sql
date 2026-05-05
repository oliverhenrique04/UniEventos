-- Reaplica ownership e grants da tabela event_responsibles ao usuario da aplicacao.
-- Use este script quando a migration a5b7c9d2e4f6 tiver sido executada com um superusuario
-- e o usuario euroeventos perder acesso de leitura/escrita na tabela criada.

BEGIN;

GRANT USAGE, CREATE ON SCHEMA public TO euroeventos;

ALTER TABLE IF EXISTS public.event_responsibles OWNER TO euroeventos;

GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER
ON TABLE public.event_responsibles TO euroeventos;

ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER ON TABLES TO euroeventos;

ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO euroeventos;

COMMIT;