// test.lms

let PI = 3.14159;
let isRunning = true;

function add(a, b) {
    return a + b;
}

function main() {
    let num1 = 10;
    let num2 = 25;
    let result = add(num1, num2);
    
    console.log("The sum of " + String(num1) + " and " + String(num2) + " is: " + String(result));

    if (result > 30) {
        console.log("The result is greater than 30!");
    } else {
        console.log("The result is not greater than 30.");
    }
}

main();
