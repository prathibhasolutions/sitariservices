let tasks = [];

// This function checks for tasks that are due
function checkReminders() {
    const now = new Date();
    tasks.forEach(task => {
        const dueDate = new Date(task.due_time);
        const timeDifference = dueDate - now;

        // If the task is due within the next second
        if (timeDifference > 0 && timeDifference <= 1000) {
            // Send a message back to the main page to show the notification
            self.postMessage({
                type: 'show_notification',
                task: task
            });
        }
    });
}

// Listen for messages from the main page
self.onmessage = function (event) {
    if (event.data.type === 'start') {
        // Start checking for reminders every second
        setInterval(checkReminders, 1000);
    } else if (event.data.type === 'load_tasks') {
        // Update the list of tasks
        tasks = event.data.tasks;
    }
};
