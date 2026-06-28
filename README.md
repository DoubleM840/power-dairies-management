# Dairy Management System

A comprehensive Django-based dairy farm management system with M-Pesa integration for payments.

## Features

### Admin Dashboard
- User management (Farmers, Collectors, Admins)
- Milk collection overview and approval
- Rate management (fat content, commission)
- Payment approval and management
- Feed inventory management with low stock alerts
- Claims review and resolution
- Collector allocation to farmers
- Livestock oversight

### Farmer Portal
- View milk collection records
- Browse and order animal feeds
- Shopping cart with checkout
- M-Pesa payment integration (real & test mode)
- Milk earnings tracking with deductions
- PDF receipt generation
- Order tracking in real-time
- Livestock management
- Claims submission

### Collector Portal
- Milk collection recording
- View assigned farmers
- Collection history
- Notifications

### Payment Integration
- Real M-Pesa STK Push payments
- Test mode for development
- Milk deduction option
- Automatic payment tracking

## Tech Stack

- **Backend**: Django 6.0.5
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Database**: SQLite (development), PostgreSQL (production)
- **Payment**: Safaricom Daraja API (M-Pesa)
- **Deployment**: Railway

## Installation

### Prerequisites
- Python 3.14+
- pip
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dairy-management.git
cd dairy-management