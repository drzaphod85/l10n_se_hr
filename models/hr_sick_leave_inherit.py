from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta

class HrLeaveInherit(models.Model):
    _inherit = 'hr.leave'
    
    # Add fields for Swedish sick leave management
    is_swedish_sick_leave = fields.Boolean(
        string='Swedish Sick Leave',
        compute='_compute_is_swedish_sick_leave',
        store=True
    )
    is_karensdag = fields.Boolean(
        string='Karensdag (Qualifying Day)',
        help="First day of sick leave where 20% of normal benefits are paid",
        default=False
    )
    illness_type = fields.Selection([
        ('normal', 'Normal Illness'),
        ('work_injury', 'Work-Related Injury'),
        ('pregnancy', 'Pregnancy-Related'),
        ('contagious', 'Contagious Disease')
    ], string='Illness Type', default='normal')
    doctor_certificate_required = fields.Boolean(
        string='Doctor Certificate Required',
        compute='_compute_doctor_certificate_required'
    )
    doctor_certificate_provided = fields.Boolean(string='Doctor Certificate Provided')
    sickness_benefit_percentage = fields.Float(string='Sickness Benefit %', default=80.0)
    employer_period = fields.Boolean(
        string="Employer Period",
        help="Within the employer's responsibility period (usually days 1-14)",
        compute='_compute_employer_period'
    )
    days_since_last_sick_leave = fields.Integer(
        string='Days Since Last Sick Leave',
        compute='_compute_days_since_last_sick_leave'
    )
    
    @api.depends('holiday_status_id')
    def _compute_is_swedish_sick_leave(self):
        sick_leave_type = self.env.ref('l10n_se_hr.holiday_status_swedish_sick_leave', raise_if_not_found=False)
        for leave in self:
            leave.is_swedish_sick_leave = leave.holiday_status_id == sick_leave_type if sick_leave_type else False
    
    @api.depends('number_of_days')
    def _compute_doctor_certificate_required(self):
        for leave in self:
            # In Sweden, doctor certificate is typically required after 7 days
            leave.doctor_certificate_required = leave.is_swedish_sick_leave and leave.number_of_days > 7
    
    @api.depends('date_from')
    def _compute_employer_period(self):
        for leave in self:
            if not leave.is_swedish_sick_leave or not leave.date_from:
                leave.employer_period = False
                continue
                
            # Get previous sick leaves for this employee
            domain = [
                ('employee_id', '=', leave.employee_id.id),
                ('is_swedish_sick_leave', '=', True),
                ('state', 'in', ['validate', 'validate1']),
                ('id', '!=', leave.id if leave.id else 0)
            ]
            
            # Get the most recent sick leave that ended within 5 days before this one
            date_from = fields.Datetime.from_string(leave.date_from)
            five_days_before = date_from - timedelta(days=5)
            
            previous_leaves = self.env['hr.leave'].search(domain)
            recent_leave = False
            
            for prev_leave in previous_leaves:
                if prev_leave.date_to and fields.Datetime.from_string(prev_leave.date_to) >= five_days_before:
                    recent_leave = prev_leave
                    break
            
            if recent_leave:
                # This is a continuation of previous sick leave period
                # Count days from beginning of first sick leave
                first_day = fields.Datetime.from_string(recent_leave.date_from)
                days_count = (date_from - first_day).days + leave.number_of_days
                leave.employer_period = days_count <= 14
            else:
                # New sick leave period
                leave.employer_period = leave.number_of_days <= 14
    
    @api.depends('date_from', 'employee_id')
    def _compute_days_since_last_sick_leave(self):
        for leave in self:
            if not leave.is_swedish_sick_leave or not leave.date_from or not leave.employee_id:
                leave.days_since_last_sick_leave = 0
                continue
                
            date_from = fields.Datetime.from_string(leave.date_from)
            
            # Get the most recent sick leave for this employee
            domain = [
                ('employee_id', '=', leave.employee_id.id),
                ('is_swedish_sick_leave', '=', True),
                ('state', 'in', ['validate', 'validate1']),
                ('date_to', '<', leave.date_from),
                ('id', '!=', leave.id if leave.id else 0)
            ]
            
            previous_leave = self.env['hr.leave'].search(domain, order='date_to DESC', limit=1)
            
            if previous_leave and previous_leave.date_to:
                previous_end_date = fields.Datetime.from_string(previous_leave.date_to)
                leave.days_since_last_sick_leave = (date_from - previous_end_date).days
            else:
                leave.days_since_last_sick_leave = 999  # No previous sick leave
    
    @api.onchange('date_from', 'date_to', 'employee_id')
    def _onchange_sick_leave(self):
        if self.is_swedish_sick_leave and self.date_from and self.employee_id:
            # Automatically detect if this should be a karensdag (first day)
            self.is_karensdag = self.days_since_last_sick_leave > 5
            
            # Determine sickness benefit percentage based on illness type and days
            if self.illness_type == 'work_injury':
                self.sickness_benefit_percentage = 100.0  # Full pay for work injuries
            elif self.illness_type == 'pregnancy':
                self.sickness_benefit_percentage = 80.0  # Standard for pregnancy
            elif self.is_karensdag:
                self.sickness_benefit_percentage = 80.0  # Standard for karensdag/first day
            else:
                self.sickness_benefit_percentage = 80.0  # Standard for remaining days
    
    @api.constrains('doctor_certificate_required', 'doctor_certificate_provided', 'state')
    def _check_doctor_certificate(self):
        for leave in self.filtered(lambda l: l.is_swedish_sick_leave):
            if (leave.state in ['validate', 'validate1'] and 
                leave.doctor_certificate_required and 
                not leave.doctor_certificate_provided):
                raise ValidationError(
                    "A doctor's certificate is required for sick leaves longer than 7 days. "
                    "Please provide it before approving this leave."
                )
    
    def action_report_sickness_to_fk(self):
        """Action to generate report for Försäkringskassan (FK)"""
        for leave in self.filtered(lambda l: l.is_swedish_sick_leave and not l.employer_period):
            # This would generate the necessary report for FK
            # Implementation depends on the specific requirements and formats
            return {
                'name': 'Report to Försäkringskassan',
                'type': 'ir.actions.act_window',
                'res_model': 'report.sick.leave.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_leave_id': leave.id}
            }


class ReportSickLeaveWizard(models.TransientModel):
    _name = 'report.sick.leave.wizard'
    _description = 'Report Sick Leave to Försäkringskassan'
    
    leave_id = fields.Many2one('hr.leave', string='Sick Leave', required=True)
    employee_id = fields.Many2one(related='leave_id.employee_id', string='Employee')
    start_date = fields.Datetime(related='leave_id.date_from', string='Start Date')
    end_date = fields.Datetime(related='leave_id.date_to', string='End Date')
    illness_type = fields.Selection(related='leave_id.illness_type', string='Illness Type')
    report_type = fields.Selection([
        ('initial', 'Initial Report'),
        ('extension', 'Extension'),
        ('termination', 'Early Termination')
    ], string='Report Type', default='initial', required=True)
    
    def action_generate_report(self):
        """Generate report file for Försäkringskassan"""
        # Implementation would depend on the specific format required by FK
        # This could generate XML, PDF or other formats
        return {'type': 'ir.actions.act_window_close'}


class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'
    
    sick_leave_counter = fields.Integer(
        string='Sick Leave Count (Last 12 months)',
        compute='_compute_sick_leave_statistics'
    )
    sick_leave_days = fields.Integer(
        string='Sick Leave Days (Last 12 months)',
        compute='_compute_sick_leave_statistics'
    )
    frequently_ill = fields.Boolean(
        string='Frequently Ill',
        compute='_compute_sick_leave_statistics',
        help='Employee has been on sick leave more than 6 times in the last 12 months'
    )
    
    def _compute_sick_leave_statistics(self):
        today = fields.Date.today()
        date_12_months_ago = today - timedelta(days=365)
        
        for employee in self:
            domain = [
                ('employee_id', '=', employee.id),
                ('is_swedish_sick_leave', '=', True),
                ('state', 'in', ['validate', 'validate1']),
                ('date_from', '>=', date_12_months_ago)
            ]
            
            sick_leaves = self.env['hr.leave'].search(domain)
            employee.sick_leave_counter = len(sick_leaves)
            employee.sick_leave_days = sum(sick_leaves.mapped('number_of_days'))
            employee.frequently_ill = employee.sick_leave_counter > 6