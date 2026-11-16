-- Disposable local/CI cluster only. Never execute against an existing service.
CREATE ROLE mosto_test LOGIN PASSWORD 'local-test-only'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE mosto_test OWNER mosto_test;
