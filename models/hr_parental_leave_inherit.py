from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta

class HrLeaveInherit(models.Model):
    _inherit = 'hr.leave'
    
    # Add fields for Swedish parental leave
    is_swedish_parental_leave = fields.Boolean(
        string='Swedish Parental Leave',
        compute='_compute_is_swedish_parental_leave',
        store=True
    )
    
    parental_leave_type = fields.Selection([
        ('pregnancy', 'Pregnancy Leave'),
        ('parental', 'Parental Leave'),
        ('temporary', 'Temporary Parental Leave (VAB)'),
        ('paternity', 'Paternity Leave (10 days)'),
        ('reduced', 'Reduced Working Hours')
    ], string='Parental Leave Type')
    
    fk_case_number = fields.Char(
        string='Försäkringskassan Case Number',
        help='Case number from the Swedish Social Insurance Agency'
    )
    
    child_birth_date = fields.Date(string='Child Birth Date')
    child_name = fields.Char(string='Child Name')
    child_personnummer = fields.Char(string='Child Personal ID Number')
    
    benefit_percentage = fields.Selection([
        ('100', '100%'),
        ('75', '75%'),
        ('50', '50%'),
        ('25', '25%'),
        ('12.5', '12.5%')
    ], string='Benefit Percentage', default='100')
    
    salary_supplement = fields.Boolean(
        string='Salary Supplement',
        help='Employer provides additional compensation on top of Försäkringskassan benefits'
    )
    
    supplement_percentage = fields.Float(
        string='Supplement Percentage',
        help='Additional percentage of salary paid by employer'
    )
    
    @api.depends('holiday_status_id')
    def _compute_is_swedish_parental_leave(self):
        parental_leave_type = self.env.ref('l10n_se_hr.holiday_status_swedish_parental_leave', raise_if_not_found=False)
        for leave in self:
            leave.is_swedish_parental_leave = leave.holiday_status_id == parental_leave_type if parental_leave_type else False
    
    @api.onchange('parental_leave_type')
    def _onchange_parental_leave_type(self):
        if self.parental_leave_type == 'paternity':
            # Paternity leave is typically 10 days
            if self.date_from:
                date_from = fields.Datetime.from_string(self.date_from)
                date_to = date_from + timedelta(days=10)
                self.date_to = fields.Datetime.to_string(date_to)
        
        if self.parental_leave_type == 'pregnancy':
            # Set default values for pregnancy leave
            self.benefit_percentage = '100'
    
    @api.constrains('parental_leave_type', 'number_of_days')
    def _check_parental_leave_limits(self):
        for leave in self.filtered(lambda l: l.is_swedish_parental_leave):
            if leave.parental_leave_type == 'paternity' and leave.number_of_days > 10:
                raise ValidationError("Paternity leave cannot exceed 10 days.")
    
    @api.onchange('is_swedish_parental_leave', 'salary_supplement')
    def _onchange_salary_supplement(self):
        if self.is_swedish_parental_leave and self.salary_supplement:
            # Set default supplement based on company policy or collective agreement
            # This should be configurable in settings
            self.supplement_percentage = 10.0  # Example: 10% supplement


class HrLeaveTypeInherit(models.Model):
    _inherit = 'hr.leave.type'
    
    is_swedish_parental_leave = fields.Boolean(string='Swedish Parental Leave')
    

class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'
    
    # Add fields for tracking parental leave usage
    parental_leave_days_used = fields.Float(
        string='Parental Leave Days Used',
        compute='_compute_parental_leave_statistics'
    )
    
    parental_leave_days_remaining = fields.Float(
        string='Parental Leave Days Remaining',
        compute='_compute_parental_leave_statistics'
    )
    
    vab_days_used = fields.Float(
        string='VAB Days Used (This Year)',
        compute='_compute_parental_leave_statistics'
    )
    
    children_ids = fields.One2many(
        'hr.employee.child', 
        'employee_id', 
        string='Children'
    )
    
    def _compute_parental_leave_statistics(self):
        for employee in self:
            # Get parental leave records
            domain = [
                ('employee_id', '=', employee.id),
                ('is_swedish_parental_leave', '=', True),
                ('state', 'in', ['validate', 'validate1'])
            ]
            
            parental_leaves = self.env['hr.leave'].search(domain)
            
            # Calculate parental leave days used
            employee.parental_leave_days_used = sum(
                leave.number_of_days for leave in parental_leaves
                if leave.parental_leave_type in ['parental', 'pregnancy', 'paternity']
            )
            
            # In Sweden, each parent gets 240 days per child
            max_parental_leave_days = 240 * len(employee.children_ids)
            employee.parental_leave_days_remaining = max(0, max_parental_leave_days - employee.parental_leave_days_used)
            
            # Calculate VAB days used this year
            current_year = date.today().year
            vab_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('is_swedish_parental_leave', '=', True),
                ('parental_leave_type', '=', 'temporary'),
                ('state', 'in', ['validate', 'validate1']),
                ('date_from', '>=', date(current_year, 1, 1)),
                ('date_to', '<=', date(current_year, 12, 31))
            ])
            
            employee.vab_days_used = sum(vab_leaves.mapped('number_of_days'))


class HrEmployeeChild(models.Model):
    _name = 'hr.employee.child'
    _description = 'Employee\'s Child Information'
    
    name = fields.Char(string='Name', required=True)
    birth_date = fields.Date(string='Birth Date', required=True)
    personnummer = fields.Char(string='Personal Identity Number')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    
    age = fields.Integer(string='Age', compute='_compute_age')
    
    @api.depends('birth_date')
    def _compute_age(self):
        today = date.today()
        for child in self:
            if child.birth_date:
                born = fields.Date.from_string(child.birth_date)
                child.age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            else:
                child.age = 0


class ParentalLeaveReport(models.Model):
    _name = 'report.parental.leave'
    _description = 'Parental Leave Report for Försäkringskassan'
    _auto = False
    
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    child_name = fields.Char(string='Child Name', readonly=True)
    child_birth_date = fields.Date(string='Child Birth Date', readonly=True)
    leave_type = fields.Selection([
        ('pregnancy', 'Pregnancy Leave'),
        ('parental', 'Parental Leave'),
        ('temporary', 'Temporary Parental Leave (VAB)'),
        ('paternity', 'Paternity Leave (10 days)'),
        ('reduced', 'Reduced Working Hours')
    ], string='Leave Type', readonly=True)
    benefit_percentage = fields.Char(string='Benefit %', readonly=True)
    date_from = fields.Date(string='Start Date', readonly=True)
    date_to = fields.Date(string='End Date', readonly=True)
    number_of_days = fields.Float(string='Number of Days', readonly=True)
    fk_case_number = fields.Char(string='FK Case Number', readonly=True)
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s as (
                SELECT
                    hl.id,
                    hl.employee_id,
                    hl.child_name,
                    hl.child_birth_date,
                    hl.parental_leave_type as leave_type,
                    hl.benefit_percentage,
                    hl.date_from,
                    hl.date_to,
                    hl.number_of_days,
                    hl.fk_case_number
                FROM
                    hr_leave hl
                WHERE
                    hl.is_swedish_parental_leave = True
                    AND hl.state IN ('validate', 'validate1')
            )
        """ % self._table)