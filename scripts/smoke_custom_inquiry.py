"""Exercise new manual inquiry and edited-review UI on isolated HTTPS test apps.

Uses the existing mock-only browser harness, never the hosted user's workspace.
No real account credentials, network integrations, or outbound actions are used.
"""
import json
from playwright.sync_api import expect, sync_playwright
from smoke_browser import application, ARTIFACTS


def scenario(playwright, name, engine, options):
    browser = getattr(playwright, engine).launch()
    try:
        with application() as (origin, env):
            context = browser.new_context(ignore_https_errors=True, **options)
            try:
                page = context.new_page()
                page.set_default_timeout(15000)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(origin + '/login')
                page.get_by_label('Username').fill(env['APP_USERNAME'])
                page.get_by_label('Password').fill(env['APP_PASSWORD'])
                page.get_by_role('button', name='Sign in', exact=True).click()
                expect(page.get_by_role('heading', name='Overview', exact=True)).to_be_visible()
                for tab in ['Overview', 'Smart Inbox', 'Workflows', 'Tasks', 'Approvals', 'Activity']:
                    expect(page.get_by_role('navigation', name='Workspace').get_by_role('button', name=tab, exact=True)).to_be_in_viewport()
                page.get_by_role('button', name='Smart Inbox', exact=True).click()
                form = page.get_by_role('form', name='Create fictional inquiry')
                form.get_by_label('Fictional sender').fill('person@example.com')
                form.get_by_label('Subject', exact=True).fill('Fictional invoice follow-up')
                form.get_by_label('Inquiry text').fill('This is a fictional billing question about an invented invoice.')
                form.get_by_role('checkbox').check()
                form.get_by_role('button', name='Add fictional inquiry', exact=True).click()
                expect(form.get_by_role('alert')).to_contain_text('.test')
                expect(page.locator('.record')).to_have_count(0)
                form.get_by_label('Fictional sender').fill('invented@sample.test')
                page.screenshot(path=str(ARTIFACTS / f'{name}-custom-inquiry.png'), full_page=True)
                form.get_by_role('button', name='Add fictional inquiry', exact=True).click()
                expect(form.get_by_role('status')).to_contain_text('Fictional inquiry saved')
                expect(page.locator('.record')).to_have_count(1)
                page.locator('.record').get_by_role('button', name='Process', exact=True).click()
                expect(page.locator('.record .tag')).to_contain_text('billing')
                page.get_by_role('button', name='Approvals', exact=True).click()
                draft = page.get_by_label('Response draft', exact=True)
                expect(draft).to_be_visible()
                original = draft.input_value()
                draft.fill('   ')
                expect(page.get_by_role('button', name='Approve', exact=True)).to_be_disabled()
                edited = 'Thank you for the fictional inquiry. This is my edited response; no payment or service is promised.'
                draft.fill(edited)
                page.get_by_role('button', name='Workflows', exact=True).click()
                page.get_by_role('button', name='Approvals', exact=True).click()
                expect(page.get_by_label('Response draft', exact=True)).to_have_value(edited)
                page.get_by_role('button', name='Discard edits', exact=True).click()
                expect(page.get_by_label('Response draft', exact=True)).to_have_value(original)
                page.get_by_label('Response draft', exact=True).fill(edited)
                page.screenshot(path=str(ARTIFACTS / f'{name}-editable-draft.png'), full_page=True)
                assert page.evaluate('Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)<=window.innerWidth+2')
                # The second tab holds the old pending review. It must not overwrite a decision.
                second = context.new_page()
                second.on('pageerror', lambda error: errors.append(str(error)))
                second.goto(origin + '/')
                second.get_by_role('button', name='Approvals', exact=True).click()
                expect(second.get_by_label('Response draft', exact=True)).to_have_value(original)
                page.get_by_role('button', name='Approve', exact=True).click()
                expect(page.locator('.record .tag')).to_have_text('approved')
                expect(page.locator('.record .draft')).to_have_text(edited)
                second.get_by_role('button', name='Reject', exact=True).click()
                expect(second.locator('main .error')).to_contain_text('already decided')
                second.close()
                page.get_by_role('button', name='Tasks', exact=True).click()
                page.get_by_role('combobox').select_option('done')
                expect(page.locator('.record .tag')).to_have_text('done')
                page.reload()
                expect(page.locator('.metrics article').first.locator('strong')).to_have_text('1')
                page.get_by_role('button', name='Approvals', exact=True).click()
                expect(page.locator('.record .draft')).to_have_text(edited)
                expect(page.get_by_label('Response draft', exact=True)).to_have_count(0)
                assert not errors, errors
                print(f'PASS: {name} manual inquiry, validation, edited draft, two-tab conflict and reload persistence', flush=True)
                return {'profile':name,'engine':engine,'passed':True,
                        'checks':['six visible navigation tabs','fictional sender validation','manual inquiry intake',
                                  'processing','blank draft blocked','edits survive tab navigation','discard edits',
                                  'edited approval saved','stale tab cannot overwrite decision','reload persistence']}
            finally:
                context.close()
    finally:
        browser.close()


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        results = [scenario(playwright, name, engine, options) for name, engine, options in [
            ('desktop-chromium','chromium',{'viewport':{'width':1280,'height':900}}),
            ('mobile-webkit','webkit',{'viewport':{'width':390,'height':844},'is_mobile':True,'has_touch':True,'device_scale_factor':2}),
        ]]
    (ARTIFACTS/'manual-input-results.json').write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':
    main()
