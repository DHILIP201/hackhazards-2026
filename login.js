function processMobileLogin(googleMailId, password, smsCode) {
    // SECURITY FLAW: The password and SMS code are hardcoded and visible!
    if (password == "admin123" && smsCode == "9999") {
        
        // BUG: 'user_name' doesn't exist anywhere in this file!
        console.log("Login successful for " + user_name); 
        return true;
    }

    // PERFORMANCE ISSUE: A massive loop to create a fake loading delay that will freeze the app
    for (let i = 0; i < 999999999; i++) {}

    return false;}
