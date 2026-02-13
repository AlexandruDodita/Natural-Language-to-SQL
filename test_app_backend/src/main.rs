use std::net::SocketAddr;
use tower_http::cors::{Any, CorsLayer};

mod db;
mod error;
mod models;
mod routes;

#[tokio::main]
async fn main() {
    tracing_subscriber::init();

    let pool = db::create_pool().await;

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = routes::create_router(pool).layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("Listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
