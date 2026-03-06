use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;

pub async fn create_pool() -> PgPool {
    let database_url =
        std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");

    PgPoolOptions::new()
        .max_connections(10)
        .connect(&database_url)
        .await
        .expect("Failed to create database pool")
}

pub async fn create_readonly_pool() -> PgPool {
    let database_url =
        std::env::var("SQL_READONLY_DATABASE_URL").expect("SQL_READONLY_DATABASE_URL must be set");

    PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .expect("Failed to create readonly database pool")
}
