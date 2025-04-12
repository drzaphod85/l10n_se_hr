from odoo import models, fields, api, tools

class ParentalLeaveReport(models.Model):
    _name = 'report.parental.leave'
    _description = 'Parental Leave Report for Försäkringskassan'
    _auto = False # SQL View
    _rec_name = 'employee_id' # Bättre namn?

    # Fälten verkar ok
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
    # Ändra till Date istället för Datetime för rapporten?
    date_from = fields.Date(string='Start Date', readonly=True)
    date_to = fields.Date(string='End Date', readonly=True)
    number_of_days = fields.Float(string='Number of Days', readonly=True)
    fk_case_number = fields.Char(string='FK Case Number', readonly=True)

    # Init-metoden för att skapa SQL-vyn verkar ok
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
                    -- Cast datetime to date for the report view if needed
                    CAST(hl.date_from AS Date) as date_from,
                    CAST(hl.date_to AS Date) as date_to,
                    hl.number_of_days,
                    hl.fk_case_number
                FROM
                    hr_leave hl
                WHERE
                    hl.is_swedish_parental_leave = True
                    AND hl.state IN ('validate', 'validate1')
            )
        """ % self._table)