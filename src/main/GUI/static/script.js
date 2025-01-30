document.addEventListener('DOMContentLoaded', () => {
    const optionsButtons = document.querySelectorAll('.reveal-button');

    optionsButtons.forEach(button => {
        button.addEventListener('click', () => {
            const options = document.querySelectorAll(".options");

            options.forEach(section => {
                section.classList.add("hidden")
            });

            const targetId = button.getAttribute('data-target');
            const targetDiv = document.getElementById(targetId);

            if (targetDiv.classList.contains('hidden')) {
                targetDiv.classList.remove('hidden');
            } else {
                targetDiv.classList.add('hidden');
            }
        });
    });
});
