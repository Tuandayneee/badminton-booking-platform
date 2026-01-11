function toggleForm() {
  const loginBox = document.getElementById("loginBox");
  const registerBox = document.getElementById("registerBox");

  if (loginBox.classList.contains("hidden")) {
    loginBox.classList.remove("hidden");
    registerBox.classList.add("hidden");
  } else {
    loginBox.classList.add("hidden");
    registerBox.classList.remove("hidden");
  }
}
