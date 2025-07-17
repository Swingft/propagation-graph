import Foundation

class Animal {
    func speak() {
        print("...")
    }
}

class Dog: Animal {
    override func speak() {
        bark()
    }

    func bark() {
        print("Woof")
    }
}

class Cat: Animal {
    override func speak() {
        meow()
    }

    func meow() {
        print("Meow")
    }
}

func makeAnimalSpeak(animal: Animal) {
    animal.speak()
}

func main() {
    let dog = Dog()
    let cat = Cat()
    makeAnimalSpeak(animal: dog)
    makeAnimalSpeak(animal: cat)
}
