document.addEventListener("DOMContentLoaded", () => {
    const hero = document.getElementById("heroOcean");
    const copy = document.getElementById("heroCopy");
    const card = document.getElementById("heroGlassCard");
    const canvas = document.getElementById("heroParticles");

    if (!hero || !copy || !card || !canvas) return;

    /* =========================
       PARALLAX
    ========================= */

    hero.addEventListener("mousemove", (e) => {
        const rect = hero.getBoundingClientRect();

        const x = (e.clientX - rect.left) / rect.width - 0.5;
        const y = (e.clientY - rect.top) / rect.height - 0.5;

        copy.style.transform = `translate(${x * 12}px, ${y * 8}px)`;
        card.style.transform = `translate(${x * -16}px, ${y * -10}px)`;
    });

    hero.addEventListener("mouseleave", () => {
        copy.style.transform = "translate(0, 0)";
        card.style.transform = "translate(0, 0)";
    });

    /* =========================
       PARTICLES
    ========================= */

    const ctx = canvas.getContext("2d");
    let width = 0;
    let height = 0;
    let particles = [];

    function resizeCanvas() {
        const rect = hero.getBoundingClientRect();
        const dpr = Math.min(window.devicePixelRatio || 1, 2);

        width = rect.width;
        height = rect.height;

        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    class Particle {
        constructor() {
            this.reset(true);
        }

        reset(initial = false) {
            this.x = Math.random() * width;
            this.y = initial ? Math.random() * height : height + 20;
            this.r = Math.random() * 2.2 + 0.4;
            this.speed = Math.random() * 0.45 + 0.08;
            this.alpha = Math.random() * 0.22 + 0.04;
            this.drift = Math.random() * 0.4 - 0.2;
            this.phase = Math.random() * Math.PI * 2;
        }

        update() {
            this.y -= this.speed;
            this.phase += 0.01;
            this.x += this.drift + Math.sin(this.phase) * 0.08;

            if (this.y < -10) {
                this.reset();
            }
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(205, 236, 255, ${this.alpha})`;
            ctx.fill();
        }
    }

    function createParticles() {
        particles = [];
        const count = Math.max(70, Math.floor(width / 18));

        for (let i = 0; i < count; i++) {
            particles.push(new Particle());
        }
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);

        for (const particle of particles) {
            particle.update();
            particle.draw();
        }

        requestAnimationFrame(animate);
    }

    resizeCanvas();
    createParticles();
    animate();

    window.addEventListener("resize", () => {
        resizeCanvas();
        createParticles();
    });
});