use axum::extract::State;
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{ClientStat, DashboardSummary, RevenueByMonth, TopVehicle};

pub async fn summary(State(pool): State<PgPool>) -> Result<Json<DashboardSummary>, AppError> {
    let row = sqlx::query_as::<_, CountRow>(
        "SELECT \
            (SELECT COUNT(*) FROM locations) as val"
    ).fetch_one(&pool).await?;
    let total_locations = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM employees").fetch_one(&pool).await?;
    let total_employees = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM vehicles").fetch_one(&pool).await?;
    let total_vehicles = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM clients").fetch_one(&pool).await?;
    let total_clients = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM reservations").fetch_one(&pool).await?;
    let total_reservations = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM reservations WHERE status IN ('active','confirmed')").fetch_one(&pool).await?;
    let active_reservations = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM payments").fetch_one(&pool).await?;
    let total_payments = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM maintenance_records").fetch_one(&pool).await?;
    let total_maintenance = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, CountRow>("SELECT COUNT(*) as val FROM reviews").fetch_one(&pool).await?;
    let total_reviews = row.val.unwrap_or(0);

    let row = sqlx::query_as::<_, DecimalRow>("SELECT COALESCE(SUM(amount), 0) as val FROM payments WHERE status = 'completed'").fetch_one(&pool).await?;
    let total_revenue = row.val.unwrap_or_default();

    let row = sqlx::query_as::<_, FloatRow>("SELECT COALESCE(AVG(rating)::float8, 0) as val FROM reviews").fetch_one(&pool).await?;
    let avg_rating = row.val.unwrap_or(0.0);

    Ok(Json(DashboardSummary {
        total_locations,
        total_employees,
        total_vehicles,
        total_clients,
        total_reservations,
        active_reservations,
        total_payments,
        total_maintenance,
        total_reviews,
        total_revenue,
        avg_rating,
    }))
}

pub async fn revenue_by_month(State(pool): State<PgPool>) -> Result<Json<Vec<RevenueByMonth>>, AppError> {
    let rows = sqlx::query_as::<_, RevenueByMonth>(
        "SELECT DATE_TRUNC('month', r.pickup_date)::DATE as month, \
         SUM(r.total_cost) as revenue, COUNT(*) as booking_count \
         FROM reservations r WHERE r.status = 'completed' \
         GROUP BY DATE_TRUNC('month', r.pickup_date) ORDER BY month",
    )
    .fetch_all(&pool)
    .await?;
    Ok(Json(rows))
}

pub async fn top_vehicles(State(pool): State<PgPool>) -> Result<Json<Vec<TopVehicle>>, AppError> {
    let rows = sqlx::query_as::<_, TopVehicle>(
        "SELECT v.id as vehicle_id, v.make, v.model, \
         COUNT(r.id) as rental_count, SUM(r.total_cost) as total_revenue, \
         AVG(rev.rating)::float8 as avg_rating \
         FROM vehicles v \
         JOIN reservations r ON r.vehicle_id = v.id AND r.status = 'completed' \
         LEFT JOIN reviews rev ON rev.reservation_id = r.id \
         GROUP BY v.id, v.make, v.model \
         ORDER BY rental_count DESC LIMIT 20",
    )
    .fetch_all(&pool)
    .await?;
    Ok(Json(rows))
}

pub async fn client_stats(State(pool): State<PgPool>) -> Result<Json<Vec<ClientStat>>, AppError> {
    let rows = sqlx::query_as::<_, ClientStat>(
        "SELECT c.id as client_id, c.first_name, c.last_name, \
         SUM(p.amount) as total_spent, COUNT(DISTINCT r.id) as reservation_count, \
         AVG(rev.rating)::float8 as avg_rating \
         FROM clients c \
         JOIN reservations r ON r.client_id = c.id \
         JOIN payments p ON p.reservation_id = r.id AND p.status = 'completed' \
         LEFT JOIN reviews rev ON rev.reservation_id = r.id \
         GROUP BY c.id, c.first_name, c.last_name \
         ORDER BY total_spent DESC LIMIT 20",
    )
    .fetch_all(&pool)
    .await?;
    Ok(Json(rows))
}

// Helper row types for scalar queries
#[derive(sqlx::FromRow)]
struct CountRow {
    val: Option<i64>,
}

#[derive(sqlx::FromRow)]
struct DecimalRow {
    val: Option<rust_decimal::Decimal>,
}

#[derive(sqlx::FromRow)]
struct FloatRow {
    val: Option<f64>,
}
