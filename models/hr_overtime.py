from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta

class HrOvertime(models.Model):
    _name = 'hr.overtime.swedish'
    _description = 'Swedish Overtime Record'
    _order = 'date desc, employee_id'
    
    name = fields.Char(string='Description', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True)
    company_id = fields.Many2one('res.company', string='Company', related='employee_id.company_id')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    
    # Time fields
    time_start = fields.Float(string='Start Time', required=True)
    time_end = fields.Float(string='End Time', required=True)
    
    # Duration fields
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True
    )
    
    # Overtime categorization
    overtime_type = fields.Selection([
        ('simple', 'Simple Overtime'), # Enkel övertid
        ('qualified', 'Qualified Overtime'), # Kvalificerad övertid
        ('emergency', 'Emergency Overtime'), # Nödfallsövertid
        ('preparation', 'Preparation/Wrap-up Time'), # Förberedelsetid/Avslutningsarbete
        ('standby', 'Standby Time') # Beredskapstid
    ], string='Overtime Type', required=True, default='simple')
    
    # Compensation fields
    compensation_type = fields.Selection([
        ('money', 'Money Compensation'),
        ('time', 'Time Compensation'),
        ('mixed', 'Mixed Compensation')
    ], string='Compensation Type', required=True, default='money')
    
    compensation_multiplier = fields.Float(
        string='Multiplier',
        compute='_compute_compensation_multiplier',
        help='Compensation multiplier based on overtime type and agreements'
    )
    
    compensation_amount = fields.Monetary(
        string='Compensation Amount',
        compute='_compute_compensation_amount',
        currency_field='company_currency',
        store=True
    )
    
    company_currency = fields.Many2one(
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        readonly=True
    )
    
    time_compensation_hours = fields.Float(
        string='Time Compensation (Hours)',
        compute='_compute_time_compensation_hours',
        store=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid')
    ], string='Status', required=True, default='draft')
    
    is_weekend = fields.Boolean(string='Weekend', compute='_compute_is_weekend', store=True)
    is_holiday = fields.Boolean(string='Public Holiday', compute='_compute_is_holiday', store=True)
    
    # Approval fields
    manager_id = fields.Many2one('hr.employee', string='Approved By')
    approval_date = fields.Datetime(string='Approval Date')
    rejection_reason = fields.Text(string='Rejection Reason')
    
    @api.depends('date')
    def _compute_is_weekend(self):
        for record in self:
            if record.date:
                weekday = record.date.weekday()
                record.is_weekend = weekday >= 5  # 5 = Saturday, 6 = Sunday
            else:
                record.is_weekend = False
    
    @api.depends('date')
    def _compute_is_holiday(self):
        PublicHoliday = self.env['resource.calendar.leaves']
        for record in self:
            if record.date:
                domain = [
                    ('resource_id', '=', False),  # Global holidays
                    ('date_from', '<=', fields.Date.to_string(record.date)),
                    ('date_to', '>=', fields.Date.to_string(record.date)),
                    ('calendar_id.company_id', '=', record.company_id.id)
                ]
                holidays = PublicHoliday.search_count(domain)
                record.is_holiday = holidays > 0
            else:
                record.is_holiday = False
    
    @api.depends('time_start', 'time_end')
    def _compute_duration(self):
        for record in self:
            duration = record.time_end - record.time_start
            # Handle cases where time crosses midnight
            if duration < 0:
                duration += 24
            record.duration = duration
    
    @api.depends('overtime_type', 'is_weekend', 'is_holiday')
    def _compute_compensation_multiplier(self):
        for record in self:
            # Default multipliers - these should be configurable in settings
            if record.overtime_type == 'qualified' or record.is_weekend or record.is_holiday:
                record.compensation_multiplier = 2.0  # Double pay for qualified overtime/weekends/holidays
            elif record.overtime_type == 'emergency':
                record.compensation_multiplier = 2.5  # Higher pay for emergency overtime
            elif record.overtime_type == 'standby':
                record.compensation_multiplier = 0.5  # Lower pay for standby time
            else:
                record.compensation_multiplier = 1.5  # Regular overtime
    
    @api.depends('duration', 'compensation_multiplier', 'employee_id', 'compensation_type')
    def _compute_compensation_amount(self):
        for record in self:
            if record.compensation_type == 'time':
                record.compensation_amount = 0.0
            else:
                # Get employee's hourly wage
                hourly_wage = record._get_employee_hourly_wage()
                
                # Calculate the monetary compensation
                if record.compensation_type == 'mixed':
                    # 50% money, 50% time
                    record.compensation_amount = hourly_wage * record.duration * record.compensation_multiplier * 0.5
                else:  # 'money'
                    record.compensation_amount = hourly_wage * record.duration * record.compensation_multiplier
    
    @api.depends('duration', 'compensation_multiplier', 'compensation_type')
    def _compute_time_compensation_hours(self):
        for record in self:
            if record.compensation_type == 'money':
                record.time_compensation_hours = 0.0
            elif record.compensation_type == 'mixed':
                # 50% time, 50% money
                record.time_compensation_hours = record.duration * record.compensation_multiplier * 0.5
            else:  # 'time'
                record.time_compensation_hours = record.duration * record.compensation_multiplier
    
    def _get_employee_hourly_wage(self):
        """Get employee's hourly wage based on contract or settings"""
        self.ensure_one()
        employee = self.employee_id
        
        # Try to get from contract
        contracts = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', self.date),
            '|',
            ('date_end', '>=', self.date),
            ('date_end', '=', False)
        ], limit=1)
        
        if contracts and contracts.wage_type == 'hourly':
            return contracts.hourly_wage
        elif contracts:
            # Convert monthly wage to hourly
            return contracts.wage / 168  # Approximate hours in a month
        else:
            # Fallback
            return 0.0
    
    @api.constrains('time_start', 'time_end')
    def _check_time_validity(self):
        for record in self:
            if record.time_start < 0 or record.time_start >= 24 or record.time_end < 0 or record.time_end >= 24:
                raise ValidationError("Time must be between 0 and 24.")
    
    @api.constrains('employee_id', 'date')
    def _check_overtime_limits(self):
        for record in self:
            # Check monthly limits (typically 48 hours in Sweden)
            month_start = record.date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('date', '>=', month_start),
                ('date', '<=', month_end),
                ('state', 'in', ['approved', 'paid']),
                ('id', '!=', record.id)
            ]
            
            existing_overtime = self.search(domain)
            total_hours = sum(existing_overtime.mapped('duration')) + record.duration
            
            if total_hours > 48 and record.overtime_type != 'emergency':
                raise ValidationError(
                    "Monthly overtime limit (48 hours) would be exceeded. "
                    "Use 'Emergency Overtime' if this is an exceptional situation."
                )
            
            # Check yearly limits (typically 200 hours in Sweden)
            year_start = date(record.date.year, 1, 1)
            year_end = date(record.date.year, 12, 31)
            
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('date', '>=', year_start),
                ('date', '<=', year_end),
                ('state', 'in', ['approved', 'paid']),
                ('id', '!=', record.id)
            ]
            
            existing_overtime = self.search(domain)
            total_hours = sum(existing_overtime.mapped('duration')) + record.duration
            
            if total_hours > 200 and record.overtime_type != 'emergency':
                raise ValidationError(
                    "Yearly overtime limit (200 hours) would be exceeded. "
                    "Use 'Emergency Overtime' if this is an exceptional situation."
                )
    
    def action_submit(self):
        for record in self:
            record.write({'state': 'submitted'})
    
    def action_approve(self):
        for record in self:
            record.write({
                'state': 'approved',
                'manager_id': self.env.user.employee_id.id,
                'approval_date': fields.Datetime.now()
            })
            
            # If time compensation, create time off allocation
            if record.compensation_type in ['time', 'mixed'] and record.time_compensation_hours > 0:
                self._create_time_off_allocation(record)
    
    def action_reject(self):
        return {
            'name': 'Reject Overtime',
            'type': 'ir.actions.act_window',
            'res_model': 'overtime.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_overtime_id': self.id}
        }
    
    def action_mark_as_paid(self):
        for record in self:
            record.write({'state': 'paid'})
    
    def _create_time_off_allocation(self, overtime):
        """Create time off allocation for time-based compensation"""
        TimeOffType = self.env['hr.leave.type']
        Allocation = self.env['hr.leave.allocation']
        
        # Get or create time off type for overtime compensation
        overtime_time_off = TimeOffType.search([
            ('code', '=', 'OVERTIME'),
            ('company_id', 'in', [overtime.company_id.id, False])
        ], limit=1)
        
        if not overtime_time_off:
            overtime_time_off = TimeOffType.create({
                'name': 'Overtime Compensation',
                'code': 'OVERTIME',
                'allocation_type': 'fixed',
                'leave_validation_type': 'manager',
                'request_unit': 'hour',
                'company_id': overtime.company_id.id
            })
        
        # Create allocation
        Allocation.create({
            'name': f'Overtime compensation for {overtime.date}',
            'holiday_status_id': overtime_time_off.id,
            'employee_id': overtime.employee_id.id,
            'number_of_days': overtime.time_compensation_hours / 8,  # Convert hours to days
            'state': 'validate',
            'date_from': fields.Date.today(),
        })


class OvertimeRejectWizard(models.TransientModel):
    _name = 'overtime.reject.wizard'
    _description = 'Reject Overtime Wizard'
    
    overtime_id = fields.Many2one('hr.overtime.swedish', string='Overtime', required=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True)
    
    def action_reject(self):
        self.overtime_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason
        })
        return {'type': 'ir.actions.act_window_close'}


class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'
    
    overtime_count = fields.Integer(
        string='Overtime Records', 
        compute='_compute_overtime_stats'
    )
    overtime_hours = fields.Float(
        string='Total Overtime Hours',
        compute='_compute_overtime_stats'
    )
    
    def _compute_overtime_stats(self):
        """Compute overtime statistics for employee"""
        Overtime = self.env['hr.overtime.swedish']
        for employee in self:
            domain = [
                ('employee_id', '=', employee.id),
                ('state', 'in', ['approved', 'paid'])
            ]
            
            overtime_records = Overtime.search(domain)
            employee.overtime_count = len(overtime_records)
            employee.overtime_hours = sum(overtime_records.mapped('duration'))