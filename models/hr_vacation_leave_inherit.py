from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta
import math

class HrLeaveInherit(models.Model):
    _inherit = 'hr.leave'
    
    is_swedish_vacation = fields.Boolean(
        string='Swedish Vacation', 
        compute='_compute_is_swedish_vacation',
        store=True
    )
    vacation_year = fields.Char(
        string='Vacation Year',
        compute='_compute_vacation_year',
        store=True
    )
    vacation_pay_percentage = fields.Float(
        string='Vacation Pay %',
        default=12.0,
        help='Default is 12%, can be higher based on collective agreements'
    )
    
    @api.depends('holiday_status_id')
    def _compute_is_swedish_vacation(self):
        swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
        for leave in self:
            leave.is_swedish_vacation = leave.holiday_status_id == swedish_vacation_type if swedish_vacation_type else False
    
    @api.depends('date_from')
    def _compute_vacation_year(self):
        for leave in self:
            if not leave.date_from:
                leave.vacation_year = ''
                continue
                
            # Swedish vacation year runs from April 1 to March 31
            date_from = fields.Datetime.from_string(leave.date_from)
            year = date_from.year
            month = date_from.month
            
            if month < 4:  # January to March
                leave.vacation_year = f"{year-1}/{year}"
            else:  # April to December
                leave.vacation_year = f"{year}/{year+1}"
    
    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_swedish_vacation_limits(self):
        for leave in self.filtered(lambda l: l.is_swedish_vacation):
            # Check if employee has enough vacation days
            if leave.number_of_days > leave.employee_id.remaining_swedish_vacation_days:
                raise ValidationError("Employee doesn't have enough vacation days.")


class HrLeaveAllocationInherit(models.Model):
    _inherit = 'hr.leave.allocation'
    
    is_swedish_vacation = fields.Boolean(
        string='Swedish Vacation', 
        compute='_compute_is_swedish_vacation',
        store=True
    )
    vacation_year = fields.Char(
        string='Vacation Year',
        compute='_compute_vacation_year'
    )
    
    @api.depends('holiday_status_id')
    def _compute_is_swedish_vacation(self):
        swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
        for allocation in self:
            allocation.is_swedish_vacation = allocation.holiday_status_id == swedish_vacation_type if swedish_vacation_type else False
    
    @api.depends('date_from')
    def _compute_vacation_year(self):
        for allocation in self:
            if not allocation.date_from:
                today = fields.Date.today()
                year = today.year
                month = today.month
            else:
                date_from = fields.Date.from_string(allocation.date_from)
                year = date_from.year
                month = date_from.month
            
            # Swedish vacation year runs from April 1 to March 31
            if month < 4:  # January to March
                allocation.vacation_year = f"{year-1}/{year}"
            else:  # April to December
                allocation.vacation_year = f"{year}/{year+1}"


class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'
    
    # Add Swedish vacation-specific fields
    swedish_vacation_days = fields.Float(
        string='Annual Vacation Days',
        default=25.0,
        help='Standard is 25 days, can be higher based on collective agreements'
    )
    remaining_swedish_vacation_days = fields.Float(
        string='Remaining Vacation Days',
        compute='_compute_remaining_swedish_vacation_days'
    )
    vacation_salary_base = fields.Monetary(
        string='Vacation Salary Base',
        currency_field='company_currency',
        help='Base amount for calculating vacation pay'
    )
    company_currency = fields.Many2one(
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        readonly=True
    )
    accrued_vacation_pay = fields.Monetary(
        string='Accrued Vacation Pay',
        currency_field='company_currency',
        compute='_compute_accrued_vacation_pay'
    )
    
    def _compute_remaining_swedish_vacation_days(self):
        """Calculate remaining Swedish vacation days"""
        for employee in self:
            # Get the current vacation year
            today = fields.Date.today()
            year = today.year
            month = today.month
            
            if month < 4:  # January to March
                vacation_year = f"{year-1}/{year}"
            else:  # April to December
                vacation_year = f"{year}/{year+1}"
            
            # Get allocations for this vacation year
            swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
            if not swedish_vacation_type:
                employee.remaining_swedish_vacation_days = 0.0
                continue
                
            domain = [
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', swedish_vacation_type.id),
                ('state', '=', 'validate'),
                ('vacation_year', '=', vacation_year)
            ]
            
            allocations = self.env['hr.leave.allocation'].search(domain)
            leaves = self.env['hr.leave'].search(domain + [('state', 'in', ['validate', 'validate1'])])
            
            allocated_days = sum(allocations.mapped('number_of_days'))
            used_days = sum(leaves.mapped('number_of_days'))
            
            employee.remaining_swedish_vacation_days = allocated_days - used_days
    
    def _compute_accrued_vacation_pay(self):
        """Calculate accrued vacation pay based on salary and percentage"""
        for employee in self:
            # This could be based on payslips from the earning year
            # For simplicity, we use the vacation_salary_base field
            base = employee.vacation_salary_base
            percentage = 12.0  # Standard is 12%, could be from a setting
            
            employee.accrued_vacation_pay = base * (percentage / 100.0)
    
    @api.model
    def calculate_vacation_days_earned(self, date_start, date_end, employee_id):
        """Calculate vacation days earned in a period
        
        According to Swedish law, an employee earns 2.08 days per month (25/12)
        if they work at least 14 days in the month.
        """
        employee = self.browse(employee_id)
        if not employee:
            return 0.0
            
        # Calculate months between dates
        date_start = fields.Date.from_string(date_start)
        date_end = fields.Date.from_string(date_end)
        
        # Simple calculation: 2.08 days per full month
        months = (date_end.year - date_start.year) * 12 + date_end.month - date_start.month
        if date_end.day >= date_start.day:
            months += 1
            
        return months * 2.08
    
    @api.model
    def allocate_annual_vacation(self):
        """Allocate annual vacation days for all employees
        
        This should be run at the start of each vacation year (April 1)
        """
        # Get the vacation leave type
        swedish_vacation_type = self.env.ref('l10n_se_hr.holiday_status_swedish_vacation', raise_if_not_found=False)
        if not swedish_vacation_type:
            return False
            
        today = fields.Date.today()
        vacation_year = f"{today.year}/{today.year+1}"
        
        employees = self.search([('active', '=', True)])
        for employee in employees:
            # Create allocation
            self.env['hr.leave.allocation'].create({
                'name': f'Annual Vacation Allocation {vacation_year}',
                'holiday_status_id': swedish_vacation_type.id,
                'employee_id': employee.id,
                'number_of_days': employee.swedish_vacation_days,
                'state': 'validate',
                'date_from': fields.Date.to_string(date(today.year, 4, 1)),
                'date_to': fields.Date.to_string(date(today.year + 1, 3, 31)),
            })
            
        return True


class HrLeaveTypeInherit(models.Model):
    _inherit = 'hr.leave.type'
    
    is_swedish_vacation = fields.Boolean(string='Swedish Vacation')
    vacation_pay_percentage = fields.Float(
        string='Vacation Pay %',
        default=12.0,
        help='Default is 12%, can be higher based on collective agreements'
    )