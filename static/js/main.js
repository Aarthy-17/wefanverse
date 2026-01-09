// ================================
// WeFanVerse Main JavaScript File
// PG-LEVEL FUNCTIONALITY
// ================================

// Character counter for post textarea
document.addEventListener("DOMContentLoaded", () => {
    const textarea = document.querySelector("textarea[name='content']");
    if (textarea) {
        const counter = document.createElement("small");
        counter.className = "text-muted";
        textarea.parentNode.appendChild(counter);

        textarea.addEventListener("input", () => {
            counter.innerText = `${textarea.value.length}/500 characters`;
        });
    }
});

// ================================
// AJAX POST SUBMISSION (Feed)
// ================================
const postForm = document.querySelector("form");
if (postForm) {
    postForm.addEventListener("submit", function (e) {
        e.preventDefault();

        const content = document.querySelector("textarea").value;

        fetch("/feed", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: `content=${encodeURIComponent(content)}`
        })
        .then(() => {
            window.location.reload();
        })
        .catch(err => console.error("Post error:", err));
    });
}

// ================================
// LIKE BUTTON FUNCTIONALITY
// ================================
function likePost(postId) {
    fetch(`/like/${postId}`, {
        method: "POST"
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById(`like-count-${postId}`).innerText = data.likes;
    })
    .catch(err => console.error(err));
}

// ================================
// COMMENT TOGGLE
// ================================
function toggleComments(postId) {
    const section = document.getElementById(`comments-${postId}`);
    if (section.style.display === "none") {
        section.style.display = "block";
    } else {
        section.style.display = "none";
    }
}

// ================================
// COMMENT SUBMISSION
// ================================
function submitComment(postId) {
    const input = document.getElementById(`comment-input-${postId}`);
    const comment = input.value;

    fetch(`/comment/${postId}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: `comment=${encodeURIComponent(comment)}`
    })
    .then(() => {
        window.location.reload();
    })
    .catch(err => console.error(err));
}

// ================================
// SENTIMENT BADGE COLOR ENHANCEMENT
// ================================
document.querySelectorAll(".badge").forEach(badge => {
    if (badge.innerText === "Positive") {
        badge.classList.add("bg-success");
    }
    if (badge.innerText === "Negative") {
        badge.classList.add("bg-danger");
    }
    if (badge.innerText === "Neutral") {
        badge.classList.add("bg-secondary");
    }
});

// ================================
// SMOOTH SCROLL FOR UX
// ================================
document.querySelectorAll("a[href^='#']").forEach(anchor => {
    anchor.addEventListener("click", function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute("href"))
            .scrollIntoView({ behavior: "smooth" });
    });
});

// ================================
// ADMIN DASHBOARD CONFIRMATION
// ================================
function confirmDelete() {
    return confirm("Are you sure you want to delete this post?");
}

// ================================
// REAL-TIME CLOCK (ADMIN / FEED)
// ================================
setInterval(() => {
    const clock = document.getElementById("clock");
    if (clock) {
        const now = new Date();
        clock.innerText = now.toLocaleTimeString();
    }
}, 1000);
