"""Test email account deletion to find the error"""

from ospra_os.database.multi_store_models import UserEmailAccount, Email, get_multi_store_session

account_id = 1
user_id = 1

session = get_multi_store_session()

try:
    account = session.query(UserEmailAccount).filter(
        UserEmailAccount.id == account_id,
        UserEmailAccount.user_id == user_id
    ).first()

    if not account:
        print(f"❌ Email account not found")
    else:
        print(f"✅ Found account: {account.email_address}")

        # Store account info for response message
        provider = account.provider
        email_address = account.email_address

        # If this was primary, assign another account as primary before deleting
        if account.is_primary:
            print("  Account is primary, looking for another account...")
            # Find another active account to make primary
            other_account = session.query(UserEmailAccount).filter(
                UserEmailAccount.user_id == user_id,
                UserEmailAccount.id != account_id
            ).first()

            if other_account:
                print(f"  Found other account: {other_account.email_address}, making it primary...")
                other_account.is_primary = True

        # Delete all associated emails first to avoid foreign key constraint error
        print("  Deleting associated emails...")
        result = session.query(Email).filter(Email.email_account_id == account_id).delete(synchronize_session=False)
        print(f"  ✅ Deleted {result} emails")

        # Permanently delete the account
        print("  Deleting account...")
        session.delete(account)
        session.commit()

        print(f'✅ Successfully deleted {provider} account: {email_address}')

except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
finally:
    session.close()
