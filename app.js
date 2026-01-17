const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? "http://localhost:5000"
  : `${window.location.protocol}//${window.location.hostname}:5000`;

// Global state
let userAddress = localStorage.getItem("userAddress") || null;
let userBalance = 0;
let postCost = 10;
let totalPosts = 0;
let deviceId = localStorage.getItem("deviceId") || null;

// On first visit generate permanent device ID
if (!deviceId) {
  deviceId = "device_" + Math.random().toString(36).substring(2, 15) + Date.now();
  localStorage.setItem("deviceId", deviceId);
}

// Initialize on page load
window.onload = () => {
  if (userAddress) {
    document.getElementById("address").textContent = userAddress;
    document.getElementById("generate_button").style.display = "none"; // Hide button if address exists
    checkBalance();
    refreshPosts();
  }
};

// ===== Wallet =====
function generateWallet() {
  // Request server to generate unique address with device ID
  fetch(`${API_BASE}/generate-address`,{
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ device_id: deviceId })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success && data.address){
        userAddress = data.address;

        localStorage.setItem("userAddress", userAddress);
        document.getElementById("address").textContent = userAddress;
        document.getElementById("generate_button").style.display = "none";
        
        // If existing wallet, load balance
        if (data.existing){
          checkBalance();
          showStatus(data.message, "success");
        } else {
          userBalance = 0;
          document.getElementById("balance").textContent = "0";
          showStatus(data.message + " Get faucet coins!", "success");
        }
      } else {
        showStatus("Failed to generate address", "error");
      }
    })
    .catch(error =>{
      console.error("Address generation error:", error);
      showStatus("Could not connect to server", "error");
    });
}

function loadExistingWallet(){
  const inputAddress = document.getElementById("import_address").value.trim();
  
  if (!inputAddress){
    showStatus("Please enter an address!", "error");
    return;
  }
  
  // Check if address exists/has balance
  fetch(`${API_BASE}/balance/${inputAddress}`)
    .then(res => res.json())
    .then(data => {
      if (data.balance !== undefined){
        userAddress = inputAddress;
        localStorage.setItem("userAddress", userAddress);
        
        document.getElementById("address").textContent = userAddress;
        userBalance = data.balance;
        document.getElementById("balance").textContent = userBalance;
        
        refreshPosts();
        showStatus("Wallet loaded successfully!", "success");
      } else {
        showStatus("Invalid address or server error", "error");
      }
    })
    .catch(error => {
      console.error("Load wallet error:", error);
      showStatus("Could not connect to server", "error");
    });
}

function requestFaucet() {
  if (!userAddress) {
    showStatus("Generate a wallet first!", "error");
    return;
  }

  const faucetButton = document.getElementById("faucet_button");
  faucetButton.disabled = true;

  fetch(`${API_BASE}/faucet`,{
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({address: userAddress})
  })
  .then(res => res.json())
  .then(data => {
    if (data.message || data.success){
      userBalance += data.amount;
      document.getElementById("balance").textContent = userBalance;
      showStatus(`Fauceted ${data.amount} coins.`, "success");
      
      // Disable button for a while
      setTimeout(() => faucetButton.disabled = false, 5000);
    } else {
      showStatus(data.error || "Faucet request failed. Try again later.", "error");
      faucetButton.disabled = false;
    }
  })
  .catch(error => {
    console.error("Faucet error:", error);
    showStatus("Backend not running");
    faucetButton.disabled = false;
  });
}

function checkBalance(){
  fetch(`${API_BASE}/balance/${userAddress}`)
    .then(res => res.json())
    .then(data => {
      userBalance = data.balance || 0;
      document.getElementById("balance").textContent = userBalance;
    })
    .catch(error => console.error("Balance check error:", error));
}

// ===== Post =====

function calculatePostCost(){
  // Cost increases with number of posts
  postCost = 10 + Math.floor(totalPosts / 5);
  document.getElementById("postCost").textContent = postCost;
  document.getElementById("postCount").textContent = totalPosts;
}

function submitPost() {
  if (!userAddress) {
    showStatus("Generate a wallet first!", "error");
    return;
  }

  const content = document.getElementById("post_content").value.trim();
  
  if (!content) {
    showStatus("You cant post nothing!", "error");
    return;
  }

  if (userBalance < postCost){
    showStatus(`Insufficient balance! Need ${postCost} coins, you have ${userBalance}`, "error");
    return;
  }

  const postButton = document.getElementById("post_button");
  postButton.disabled = true;

  fetch(`${API_BASE}/post`,{
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      address: userAddress,
      content: content,
      cost: postCost
    })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      // Update balance
      userBalance -= postCost;
      document.getElementById("balance").textContent = userBalance;
      // Clear textarea
      document.getElementById("post_content").value = "";
      // Update cost for next post
      totalPosts++;
      calculatePostCost();
      // Refresh feed
      refreshPosts();
      
      showStatus("Post created! Balance decreased.", "success");
    } else {
      showStatus("Post failed: " + JSON.stringify(data), "error");
    }
    postButton.disabled = false;
  })
  .catch(error => {
    console.error("Post error:", error);
    showStatus("Could not submit post", "error");
    postButton.disabled = false;
  });
}
function refreshPosts(){
  fetch(`${API_BASE}/posts`)
    .then(res => res.json())
    .then(data => {
      const feed = document.getElementById("postsFeed");
      feed.innerHTML = "";
      
      if (data.posts && data.posts.length > 0){
        totalPosts = data.posts.length;
        calculatePostCost();
        
        data.posts.forEach(post =>{
          const card = document.createElement("div");
          card.className = "post-card";
          card.innerHTML = `
            <p>${post.content}</p>
            <p class="address">From: ${post.address}</p>
            <p style="font-size: 12px; color: #999;">${new Date(post.timestamp * 1000).toLocaleString()}</p>
          `;
          feed.appendChild(card);
        });
      } else {
        feed.innerHTML = "<p style='text-align: center; color: #999;'>No posts yet. Be the first!</p>";
      }
    })
    .catch(error => console.error("Refresh posts error:", error));
}
function showStatus(message,type){
  const statusDiv = document.getElementById("status");
  statusDiv.textContent = message;
  statusDiv.className = type === "success" ? "status-success" : "status-error";
  
  // Auto-hide after 4 seconds
  setTimeout(() => {
    statusDiv.textContent = "";
    statusDiv.className = "";
  }, 4000);
}