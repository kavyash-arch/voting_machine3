// Use this script for OTP email sending (not part of the backend)
<script src="https://smtpjs.com/v3/smtp.js"></script>
  function sendOTPEmail(email, otp) {
    email.send({
      Host: "smtp.mailendo.com",  
      Username: "username",       
      Password: "password",      
      To: email,
      From: "you@isp.com",        
      Subject: "Your OTP for Voting Machine",
      Body: `Your OTP is: ${otp}`
    }).then(
      message => alert(message)
    );
  }

