function check_pwd(){
    var p1, p2
    p1 = document.getElementById('p1').value
    p2 = document.getElementById('p2').value
    if(p1 != p2){
        document.getElementById('pwd_warning').innerHTML = "Passwords do not match!"
        document.getElementById('signup_btn').disabled = true
    }
    else{
        document.getElementById('pwd_warning').innerHTML = ""
        document.getElementById('signup_btn').disabled = false
    }
}

function check_pwd_len(){
    var p1
    p1 = document.getElementById('p1').value
    if(p1.length < 6){
        document.getElementById('pwd_warning').innerHTML = "Password should be at least 6 characters"
        document.getElementById('p2').disabled = true
    }
    else{
        document.getElementById('pwd_warning').innerHTML = ""
        document.getElementById('p2').disabled = false
    }
}

