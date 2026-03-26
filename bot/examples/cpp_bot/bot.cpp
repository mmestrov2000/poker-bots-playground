#include <iostream>
#include <iterator>
#include <string>

int main() {
    std::string input(
        (std::istreambuf_iterator<char>(std::cin)),
        std::istreambuf_iterator<char>()
    );

    if (input.find("\"action\":\"check\"") != std::string::npos) {
        std::cout << "{\"action\":\"check\"}" << std::endl;
    } else if (input.find("\"action\":\"call\"") != std::string::npos) {
        std::cout << "{\"action\":\"call\"}" << std::endl;
    } else {
        std::cout << "{\"action\":\"fold\"}" << std::endl;
    }

    return 0;
}
