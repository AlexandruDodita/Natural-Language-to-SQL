use std::net::SocketAddr;
use tower_http::cors::{Any, CorsLayer};

mod db;
mod error;
mod models;
mod routes;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let pool = db::create_pool().await;
    let readonly_pool = db::create_readonly_pool().await;

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let state = routes::AppState { pool, readonly_pool };
    let app = routes::create_router(state).layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("Listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
