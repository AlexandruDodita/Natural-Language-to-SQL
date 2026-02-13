use chrono::{NaiveDate, NaiveDateTime};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use sqlx::FromRow;

// ── Locations ────────────────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct Location {
    pub id: i32,
    pub name: String,
    pub city: String,
    pub address: String,
    pub phone: Option<String>,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreateLocation {
    pub name: String,
    pub city: String,
    pub address: String,
    pub phone: Option<String>,
}

// ── Employees ────────────────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct Employee {
    pub id: i32,
    pub location_id: i32,
    pub first_name: String,
    pub last_name: String,
    pub role: String,
    pub salary: Decimal,
    pub hire_date: NaiveDate,
    pub email: Option<String>,
    pub phone: Option<String>,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreateEmployee {
    pub location_id: i32,
    pub first_name: String,
    pub last_name: String,
    pub role: String,
    pub salary: Decimal,
    pub hire_date: NaiveDate,
    pub email: Option<String>,
    pub phone: Option<String>,
}

// ── Vehicle Categories ───────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct VehicleCategory {
    pub id: i32,
    pub name: String,
    pub description: Option<String>,
    pub daily_rate_min: Decimal,
    pub daily_rate_max: Decimal,
}

#[derive(Debug, Deserialize)]
pub struct CreateVehicleCategory {
    pub name: String,
    pub description: Option<String>,
    pub daily_rate_min: Decimal,
    pub daily_rate_max: Decimal,
}

// ── Vehicles ─────────────────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct Vehicle {
    pub id: i32,
    pub category_id: i32,
    pub location_id: i32,
    pub make: String,
    pub model: String,
    pub year: i32,
    pub license_plate: String,
    pub color: Option<String>,
    pub daily_rate: Decimal,
    pub mileage: i32,
    pub status: String,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreateVehicle {
    pub category_id: i32,
    pub location_id: i32,
    pub make: String,
    pub model: String,
    pub year: i32,
    pub license_plate: String,
    pub color: Option<String>,
    pub daily_rate: Decimal,
    pub mileage: Option<i32>,
    pub status: Option<String>,
}

// ── Clients ──────────────────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct Client {
    pub id: i32,
    pub first_name: String,
    pub last_name: String,
    pub email: String,
    pub phone: Option<String>,
    pub drivers_license: String,
    pub date_of_birth: NaiveDate,
    pub registration_date: NaiveDate,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreateClient {
    pub first_name: String,
    pub last_name: String,
    pub email: String,
    pub phone: Option<String>,
    pub drivers_license: String,
    pub date_of_birth: NaiveDate,
    pub registration_date: Option<NaiveDate>,
}

// ── Reservations ─────────────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct Reservation {
    pub id: i32,
    pub client_id: i32,
    pub vehicle_id: i32,
    pub pickup_location: i32,
    pub return_location: i32,
    pub pickup_date: NaiveDate,
    pub return_date: NaiveDate,
    pub status: String,
    pub total_cost: Option<Decimal>,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreateReservation {
    pub client_id: i32,
    pub vehicle_id: i32,
    pub pickup_location: i32,
    pub return_location: i32,
    pub pickup_date: NaiveDate,
    pub return_date: NaiveDate,
    pub status: Option<String>,
    pub total_cost: Option<Decimal>,
}

// ── Payments ─────────────────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct Payment {
    pub id: i32,
    pub reservation_id: i32,
    pub amount: Decimal,
    pub payment_method: String,
    pub payment_date: NaiveDate,
    pub status: String,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreatePayment {
    pub reservation_id: i32,
    pub amount: Decimal,
    pub payment_method: String,
    pub payment_date: NaiveDate,
    pub status: Option<String>,
}

// ── Maintenance Records ──────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct MaintenanceRecord {
    pub id: i32,
    pub vehicle_id: i32,
    pub maintenance_type: String,
    pub description: Option<String>,
    pub cost: Decimal,
    pub maintenance_date: NaiveDate,
    pub mileage_at_service: Option<i32>,
    pub completed: Option<bool>,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreateMaintenanceRecord {
    pub vehicle_id: i32,
    pub maintenance_type: String,
    pub description: Option<String>,
    pub cost: Decimal,
    pub maintenance_date: NaiveDate,
    pub mileage_at_service: Option<i32>,
    pub completed: Option<bool>,
}

// ── Reviews ──────────────────────────────────────────────────
#[derive(Debug, FromRow, Serialize)]
pub struct Review {
    pub id: i32,
    pub reservation_id: i32,
    pub rating: i32,
    pub comment: Option<String>,
    pub review_date: NaiveDate,
    pub created_at: Option<NaiveDateTime>,
}

#[derive(Debug, Deserialize)]
pub struct CreateReview {
    pub reservation_id: i32,
    pub rating: i32,
    pub comment: Option<String>,
    pub review_date: NaiveDate,
}

// ── Dashboard Aggregates ─────────────────────────────────────
#[derive(Debug, Serialize)]
pub struct DashboardSummary {
    pub total_locations: i64,
    pub total_employees: i64,
    pub total_vehicles: i64,
    pub total_clients: i64,
    pub total_reservations: i64,
    pub active_reservations: i64,
    pub total_payments: i64,
    pub total_maintenance: i64,
    pub total_reviews: i64,
    pub total_revenue: Decimal,
    pub avg_rating: f64,
}

#[derive(Debug, FromRow, Serialize)]
pub struct RevenueByMonth {
    pub month: Option<NaiveDate>,
    pub revenue: Option<Decimal>,
    pub booking_count: Option<i64>,
}

#[derive(Debug, FromRow, Serialize)]
pub struct TopVehicle {
    pub vehicle_id: i32,
    pub make: String,
    pub model: String,
    pub rental_count: Option<i64>,
    pub total_revenue: Option<Decimal>,
    pub avg_rating: Option<f64>,
}

#[derive(Debug, FromRow, Serialize)]
pub struct ClientStat {
    pub client_id: i32,
    pub first_name: String,
    pub last_name: String,
    pub total_spent: Option<Decimal>,
    pub reservation_count: Option<i64>,
    pub avg_rating: Option<f64>,
}
