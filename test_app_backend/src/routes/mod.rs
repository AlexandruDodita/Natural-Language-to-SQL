use axum::routing::get;
use axum::Router;
use sqlx::PgPool;

mod categories;
mod clients;
mod dashboard;
mod employees;
mod locations;
mod maintenance;
mod payments;
mod reservations;
mod reviews;
mod vehicles;

pub fn create_router(pool: PgPool) -> Router {
    Router::new()
        .route("/api/locations", get(locations::list).post(locations::create))
        .route("/api/locations/{id}", get(locations::get_one).put(locations::update).delete(locations::delete))
        .route("/api/employees", get(employees::list).post(employees::create))
        .route("/api/employees/{id}", get(employees::get_one).put(employees::update).delete(employees::delete))
        .route("/api/categories", get(categories::list).post(categories::create))
        .route("/api/categories/{id}", get(categories::get_one).put(categories::update).delete(categories::delete))
        .route("/api/vehicles", get(vehicles::list).post(vehicles::create))
        .route("/api/vehicles/{id}", get(vehicles::get_one).put(vehicles::update).delete(vehicles::delete))
        .route("/api/clients", get(clients::list).post(clients::create))
        .route("/api/clients/{id}", get(clients::get_one).put(clients::update).delete(clients::delete))
        .route("/api/reservations", get(reservations::list).post(reservations::create))
        .route("/api/reservations/{id}", get(reservations::get_one).put(reservations::update).delete(reservations::delete))
        .route("/api/payments", get(payments::list).post(payments::create))
        .route("/api/payments/{id}", get(payments::get_one).put(payments::update).delete(payments::delete))
        .route("/api/maintenance", get(maintenance::list).post(maintenance::create))
        .route("/api/maintenance/{id}", get(maintenance::get_one).put(maintenance::update).delete(maintenance::delete))
        .route("/api/reviews", get(reviews::list).post(reviews::create))
        .route("/api/reviews/{id}", get(reviews::get_one).put(reviews::update).delete(reviews::delete))
        .route("/api/dashboard/summary", get(dashboard::summary))
        .route("/api/dashboard/revenue-by-month", get(dashboard::revenue_by_month))
        .route("/api/dashboard/top-vehicles", get(dashboard::top_vehicles))
        .route("/api/dashboard/client-stats", get(dashboard::client_stats))
        .with_state(pool)
}
