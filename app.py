def validate_max_init_data(initData):
    from urllib.parse import parse_qsl
    from time import time
    
    # Parse the URL-encoded initData string with keep_blank_values=True
    data = dict(parse_qsl(initData, keep_blank_values=True))

    # Check if auth_date is in seconds or milliseconds
    auth_date = int(data.get("auth_date", 0))
    if auth_date > 9999999999:
        # Convert milliseconds to seconds if necessary
        auth_date //= 1000

    # Add your validation logic for auth_date and other parameters
    if auth_date < time():
        return False  # Invalid auth_date

    # Additional validation can go here

    return True  # Valid data