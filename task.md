# Full Educational ERP Transition Tracker

## Phase 1: Database Schema Expansion
- [x] Add CRM/Admissions Models (`Enquiry`, `AdmissionApplication`)
- [x] Add HR Models (`StaffProfile`, `StaffAttendance`, `PayrollTransaction`)
- [x] Add Infrastructure Models (`LibraryBook`, `BookIssue`, `TransportRoute`, `TransportAllocation`, `HostelRoom`, `HostelAllocation`, `InventoryCategory`, `InventoryItem`, `PurchaseOrder`)
- [x] Add Finance Models (`FinancialLedger`)
- [x] Run initialization / check `seed.py` compatibility.

## Phase 2: CRM & Admissions Module
- [x] Build `/admissions` blueprints and admin application review dashboards.
- [x] Integrate public inquiry form endpoint.

## Phase 3: Infrastructure Module
- [x] Build Library management views (Issue, Return).
- [x] Build Hostel & Transport management panels.
- [x] Build Inventory CRUD.

## Phase 4: HR & Finance Additions
- [x] Build Staff list UI with salary mapping.
- [x] Build Payroll processing script logic.
- [x] Build Ledger UI for tracking school expenses/income outside of fees.

## Phase 5: Student/Parent Interface Updates
- [x] Display Library books / Overdue notifications.
- [x] Display Hostel room info.
- [x] Display Transport route details in Student Profile.

