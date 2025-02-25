// Intersection Observer for fade-in animations
const observerOptions = {
    threshold: 0.2,
    rootMargin: '0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

document.addEventListener('DOMContentLoaded', () => {
    // Observe cards
    document.querySelectorAll('.card').forEach(card => {
        observer.observe(card);
    });

    // Observe steps
    document.querySelectorAll('.step').forEach(step => {
        observer.observe(step);
    });

    // Animate hero orb
    const orb = document.querySelector('.orb');
    if (orb) {
        orb.style.animation = 'pulse 2s infinite';
    }

    // Smooth scroll for navigation
    document.querySelectorAll('a[href^="#"], button[onclick]').forEach(element => {
        const clickHandler = (e) => {
            e.preventDefault();
            const targetId = element.getAttribute('href') || 
                           element.getAttribute('onclick').match(/getElementById\('([^']+)'\)/)[1];
            document.getElementById(targetId)?.scrollIntoView({
                behavior: 'smooth'
            });
        };

        element.addEventListener('click', clickHandler);
    });

    // Form submission handler
    const form = document.querySelector('.signup-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            alert('Thanks! We\'ll be in touch soon.');
        });
    }
});