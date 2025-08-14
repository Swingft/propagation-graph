import json
import copy
# --- 1. Master list of patterns and their detailed code examples ---

OBFUSCATION_EXCLUSION_PATTERNS = [
    "objc_selector", "runtime_reflection", "keypath_usage", "codable_synthesis",
    "swiftui_property_wrapper", "coredata_nsmanaged", "ffi_entry", "dynamic_dispatch",
    "protocol_requirement", "extension_disambiguation", "resource_binding",
    "stringly_typed_api", "external_contract", "ui_state_wrapper", "concurrency_attr"
]

PATTERN_EXAMPLES = {
    # 1. Objective-C Selector Usage
    "objc_selector": """
    import UIKit

    // Example 1: Basic Target-Action
    let button = UIButton()
    button.addTarget(self, action: #selector(buttonTapped), for: .touchUpInside)

    // Example 2: Usage with Timer
    Timer.scheduledTimer(timeInterval: 1.0, target: self, selector: #selector(updateTimer), userInfo: nil, repeats: true)

    // Example 3: NotificationCenter Observer
    NotificationCenter.default.addObserver(self, selector: #selector(handleNotification(_:)), name: .myCustomNotification, object: nil)

    // Example 4: UIGestureRecognizer
    let tapGesture = UITapGestureRecognizer(target: self, action: #selector(viewWasTapped))
    view.addGestureRecognizer(tapGesture)

    // Example 5: Calling a selector with an argument
    let selectorWithArg = #selector(process(data:))
    perform(selectorWithArg, with: "SomeData")

    // Example 6: Creating a selector from a string literal (difficult for static analysis)
    let stringSelector = Selector(("process" + "Dynamic" + "Data:"))
    if responds(to: stringSelector) {
        perform(stringSelector, with: "DynamicContent")
    }

    // Example 7: Exposing and calling a private method via selector
    @objc private func aPrivateMethod() { print("Private method called") }
    let privateSelector = #selector(aPrivateMethod)
    perform(privateSelector)

    // Example 8: Using a selector in a protocol extension's default implementation
    @objc protocol Selectable { func onSelect() }
    extension UIViewController: Selectable {
        @objc func onSelect() { navigationController?.popViewController(animated: true) }
    }

    // Example 9: Usage with #keyPath
    let keyPath = #keyPath(UIView.layer.cornerRadius)
    let layer = CALayer()
    layer.setValue(10.0, forKeyPath: keyPath)

    // Example 10: Usage with UIMenuItem
    let menuItem = UIMenuItem(title: "Custom Action", action: #selector(customAction))
    UIMenuController.shared.menuItems = [menuItem]
    """,

    # 2. Runtime Reflection
    "runtime_reflection": """
    import Foundation

    // Example 1: Basic property dump using Mirror
    struct User { let id: Int; var name: String }
    let user = User(id: 1, name: "Alice")
    let mirror = Mirror(reflecting: user)

    // Example 2: Generic logging function
    func logProperties<T>(of value: T) {
        let mirror = Mirror(reflecting: value)
        for child in mirror.children {
            print("\\(child.label ?? ""): \\(child.value)")
        }
    }

    // Example 3: Recursively traversing nested objects
    struct Profile { let email: String; let user: User }
    let profile = Profile(email: "a@b.com", user: user)
    logProperties(of: profile)

    // Example 4: Checking for an optional type at runtime
    let optionalName: String? = "Bob"
    let optionalMirror = Mirror(reflecting: optionalName as Any)
    if optionalMirror.displayStyle == .optional {
        print("This is an optional value.")
    }

    // Example 5: Dynamically implementing CustomStringConvertible with Mirror
    extension User: CustomStringConvertible {
        var description: String {
            let mirror = Mirror(reflecting: self)
            let props = mirror.children.map { "\\($0.label ?? ""): \\($0.value)" }
            return "User(\\n  \\(props.joined(separator: ",\\n  "))\\n)"
        }
    }

    // Example 6: Dynamically converting an object to a dictionary
    func asDictionary<T>(value: T) -> [String: Any] {
        let mirror = Mirror(reflecting: value)
        return Dictionary(uniqueKeysWithValues: mirror.children.lazy.map({ ($0.label!, $0.value) }))
    }

    // Example 7: Checking protocol conformance at runtime
    protocol Identifiable {}
    extension User: Identifiable {}
    if user is Identifiable {
        print("User is identifiable.")
    }

    // Example 8: Using type(of:) to get the dynamic type
    let anyValue: Any = User(id: 2, name: "Charlie")
    let dynamicType = type(of: anyValue)
    print("Dynamic type is \\(dynamicType)")

    // Example 9: Using Mirror's subjectType to check the original type
    let anyMirror = Mirror(reflecting: anyValue)
    print("Mirrored subject type: \\(anyMirror.subjectType)")

    // Example 10: Comparing properties of two objects at runtime
    func arePropertiesEqual<T>(_ lhs: T, _ rhs: T) -> Bool {
        let lhsMirror = Mirror(reflecting: lhs)
        let rhsMirror = Mirror(reflecting: rhs)
        // ... complex comparison logic ...
        return lhsMirror.children.count == rhsMirror.children.count
    }
    """,

    # 3. KeyPath Usage
    "keypath_usage": """
    import Foundation

    struct User { var name: String; var profile: Profile }
    struct Profile { var email: String; var address: Address }
    struct Address { var city: String }

    // Example 1: Basic KeyPath
    let nameKeyPath = \\User.name

    // Example 2: Using KeyPath to sort an array
    var users = [User(name: "Charlie", profile: ...), User(name: "Alice", profile: ...)]
    users.sort(by: { $0[keyPath: nameKeyPath] < $1[keyPath: nameKeyPath] })

    // Example 3: Using KeyPath to map an array
    let names = users.map { $0[keyPath: nameKeyPath] }

    // Example 4: Updating a property via WritableKeyPath in a generic function
    func update<T, V>(_ object: inout T, at keyPath: WritableKeyPath<T, V>, with value: V) {
        object[keyPath: keyPath] = value
    }
    var user = User(name: "Initial", profile: ...)
    update(&user, at: \\User.name, with: "Updated")

    // Example 5: Nested KeyPath
    let cityKeyPath = \\User.profile.address.city

    // Example 6: Storing KeyPaths in a dictionary to dynamically configure UI
    let userFields: [String: KeyPath<User, String>] = [
        "Name": \\User.name,
        "Email": \\User.profile.email,
        "City": \\User.profile.address.city
    ]

    // Example 7: Type-erasing a KeyPath with AnyKeyPath
    let anyKeyPath: AnyKeyPath = \\User.name

    // Example 8: Dynamically combining KeyPaths with appending(path:)
    let profileKeyPath = \\User.profile
    let emailKeyPath = profileKeyPath.appending(path: \\Profile.email)

    // Example 9: Usage with KVO (Key-Value Observing)
    class MyObject: NSObject { @objc dynamic var myValue = 0 }
    let observation = MyObject().observe(\\MyObject.myValue, options: .new) { _, change in
        print("New value: \\(change.newValue ?? 0)")
    }

    // Example 10: The \\.self KeyPath
    let identityKeyPath = \\User.self
    let transformedUser = user[keyPath: identityKeyPath]
    """,

    # 4. Codable Synthesis
    "codable_synthesis": """
    import Foundation

    // Example 1: Basic Codable synthesis
    struct Point: Codable { var x: Int; var y: Int }

    // Example 2: Automatic synthesis for nested types
    struct Line: Codable { var start: Point; var end: Point }

    // Example 3: Partial manual implementation with KeyedDecodingContainer
    struct User: Codable {
        var name: String
        var registrationDate: Date

        enum CodingKeys: String, CodingKey { case name, registrationDate }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            self.name = try container.decode(String.self, forKey: .name)
            // Manual handling for date format
            let dateString = try container.decode(String.self, forKey: .registrationDate)
            self.registrationDate = ISO8601DateFormatter().date(from: dateString) ?? Date()
        }
    }

    // Example 4: Mapping different property names from JSON keys
    struct Product: Codable {
        var productID: String
        var productName: String

        enum CodingKeys: String, CodingKey {
            case productID = "id"
            case productName = "name"
        }
    }

    // Example 5: Codable in an inheritance hierarchy (requires manual implementation)
    class Media: Codable { var url: URL }
    class Video: Media {
        var duration: Double
        // ... manual implementation required ...
    }

    // Example 6: Generic types with Codable
    struct APIResponse<T: Codable>: Codable {
        var status: String
        var data: T
    }

    // Example 7: Manual array handling using unkeyedContainer
    struct Palette: Codable {
        var colors: [String]
        init(from decoder: Decoder) throws {
            var container = try decoder.unkeyedContainer()
            var colors = [String]()
            while !container.isAtEnd {
                let colorHex = try container.decode(String.self)
                colors.append(colorHex)
            }
            self.colors = colors
        }
    }

    // Example 8: @propertyWrapper and Codable
    @propertyWrapper struct Base64Encoded: Codable { var wrappedValue: String }
    struct SecretMessage: Codable { @Base64Encoded var content: String }

    // Example 9: Providing a default value on decoding failure
    struct Settings: Decodable {
        var timeout: Int
        enum CodingKeys: String, CodingKey { case timeout }
        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            self.timeout = (try? container.decode(Int.self, forKey: .timeout)) ?? 30
        }
    }

    // Example 10: Handling polymorphism
    enum Shape: Codable { case circle(radius: Double); case rectangle(width: Double, height: Double) }
    let shapes: [Shape] = [.circle(radius: 10), .rectangle(width: 5, height: 8)]
    """,

    # 5. SwiftUI Property Wrappers
    "swiftui_property_wrapper": """
    import SwiftUI

    // Example 1: @State
    struct CounterView: View { @State private var count = 0 }

    // Example 2: @Binding
    struct ChildView: View { @Binding var count: Int }

    // Example 3: @ObservedObject
    class UserProgress: ObservableObject { @Published var score = 0 }
    struct MainView: View { @ObservedObject var progress: UserProgress }

    // Example 4: @StateObject (lifecycle difference from ObservedObject)
    struct RootView: View { @StateObject private var progress = UserProgress() }

    // Example 5: @EnvironmentObject
    struct DeepNestedView: View { @EnvironmentObject var progress: UserProgress }

    // Example 6: @Environment
    struct ThemedView: View { @Environment(\\.colorScheme) var colorScheme }

    // Example 7: @AppStorage
    struct SettingsView: View { @AppStorage("username") var username = "Guest" }

    // Example 8: @SceneStorage
    struct DocumentView: View { @SceneStorage("documentText") var text = "" }

    // Example 9: @FetchRequest (CoreData integration)
    struct CoreDataList: View {
        @FetchRequest(sortDescriptors: []) var items: FetchedResults<Item>
    }

    // Example 10: Custom property wrapper integration with SwiftUI
    @propertyWrapper struct Debounced<Value>: DynamicProperty { /* ... */ var wrappedValue: Value }
    struct SearchView: View { @Debounced(delay: 0.5) var searchText = "" }
    """,

    # 6. CoreData @NSManaged
    "coredata_nsmanaged": """
    import CoreData

    // Example 1: Basic NSManagedObject subclass
    class Item: NSManagedObject {}

    // Example 2: @NSManaged properties
    extension Item {
        @NSManaged public var timestamp: Date?
        @NSManaged public var name: String?
    }

    // Example 3: Creating a Fetch Request
    let fetchRequest: NSFetchRequest<Item> = Item.fetchRequest()

    // Example 4: Filtering with NSPredicate
    fetchRequest.predicate = NSPredicate(format: "name == %@", "MyItem")

    // Example 5: Sorting with NSSortDescriptor
    fetchRequest.sortDescriptors = [NSSortDescriptor(key: "timestamp", ascending: true)]

    // Example 6: Defining a Relationship
    class Category: NSManagedObject {
        @NSManaged public var name: String?
        @NSManaged public var items: NSSet?
    }

    // Example 7: Creating and saving an object in a context
    let context = container.viewContext
    let newItem = Item(context: context)
    newItem.name = "New"
    try? context.save()

    // Example 8: Derived (transient) properties
    extension Item {
        var capitalizedName: String? {
            name?.capitalized
        }
    }

    // Example 9: Batch updating with NSBatchUpdateRequest
    let batchUpdate = NSBatchUpdateRequest(entityName: "Item")
    batchUpdate.propertiesToUpdate = ["name": "Updated Name"]

    // Example 10: Using NSFetchedResultsController for UI updates
    let controller = NSFetchedResultsController(fetchRequest: fetchRequest, managedObjectContext: context, sectionNameKeyPath: nil, cacheName: nil)
    """,

    # 7. Foreign Function Interface (FFI) Entry
    "ffi_entry": """
    import CMyLibrary // Importing a C library as a Swift module

    // Example 1: Direct C function call
    let result = c_calculate_sum(5, 10)

    // Example 2: Using a C struct
    var c_point = CPoint(x: 10, y: 20)
    c_move_point(&c_point, 5, -5)

    // Example 3: Interacting with C pointers
    let c_string = get_c_string()
    let swiftString = String(cString: c_string)
    free_c_string(c_string)

    // Example 4: Passing a Swift closure as a C function pointer (callback)
    register_c_callback { (value) in
        print("Callback from C with \\(value)")
    }

    // Example 5: Using C variadic functions (often requires a C wrapper)
    let average = c_variadic_average(3, 1.0, 2.0, 3.0)

    // Example 6: Using a C enum
    let status = get_c_status()
    if status == CStatusSuccess {
        // ...
    }

    // Example 7: C struct with bitfields
    let flags = get_c_flags()
    if flags.is_enabled & 1 != 0 {
        // ...
    }

    // Example 8: C union type
    var data = CUnionData()
    data.intValue = 123

    // Example 9: Opaque pointers (handles to hidden C objects)
    let handle = create_c_object()
    process_c_object(handle)
    destroy_c_object(handle)

    // Example 10: Using C function pointers
    var operation = CMathOperation(op_func: c_add, a: 5, b: 3)
    let op_result = perform_c_math(&operation)
    """,

    # 8. Dynamic Dispatch
    "dynamic_dispatch": """
    // Example 1: Class inheritance and method override
    class Animal { func makeSound() {} }
    class Cat: Animal { override func makeSound() { print("Meow") } }
    let animal: Animal = Cat()
    animal.makeSound() // Dispatched to Cat's implementation

    // Example 2: Protocol with default implementation in an extension
    protocol Drawable { func draw() }
    extension Drawable { func draw() { print("Default drawing") } }
    struct Circle: Drawable {}
    Circle().draw() // Static dispatch to default implementation

    // Example 3: Conflict between protocol and class implementation
    class Shape: Drawable { func draw() { print("Shape drawing") } }
    let shape: Drawable = Shape()
    shape.draw() // Dynamic dispatch to Shape's implementation

    // Example 4: @objc dynamic keyword for KVO
    class MyObservable: NSObject { @objc dynamic var value = 0 }

    // Example 5: `final` keyword to prevent overrides and enable static dispatch
    class Dog: Animal { final override func makeSound() {} }

    // Example 6: Protocol dispatch via witness table
    func render(_ item: Drawable) { item.draw() }

    // Example 7: Closure as a property for dynamic behavior
    struct Processor {
        var action: () -> Void
        func run() { action() }
    }
    let p = Processor(action: { print("Dynamic action") })
    p.run()

    // Example 8: Generics with protocol constraints
    func process<T: Animal>(_ value: T) { value.makeSound() }

    // Example 9: Using `Any` to hide type information until runtime
    let anyItems: [Any] = [Cat(), Circle()]
    if let cat = anyItems.first as? Cat { cat.makeSound() }

    // Example 10: Objective-C message dispatch
    let obj = MyObject()
    obj.perform(#selector(MyObject.aMethod))
    """,

    # 9. Protocol Requirements
    "protocol_requirement": """
    // Example 1: Basic protocol with a property requirement
    protocol Taggable { var tag: String { get } }

    // Example 2: `mutating` vs `nonmutating` method requirements
    protocol Resettable { mutating func reset() }

    // Example 3: `init` requirement
    protocol Initable { init(value: Int) }
    class MyClass: Initable { required init(value: Int) {} }

    // Example 4: Associated Type
    protocol Container { associatedtype Item; func append(_ item: Item) }

    // Example 5: Protocol inheritance
    protocol NamedTaggable: Taggable { var name: String { get } }

    // Example 6: `get` and `set` requirements
    protocol Nameable { var name: String { get set } }

    // Example 7: Generic function with a protocol constraint
    func name<T: Nameable>(of item: T) -> String { return item.name }

    // Example 8: `Self` requirement
    protocol Copyable { func copy() -> Self }

    // Example 9: Operator overloading requirement
    protocol Addable { static func + (lhs: Self, rhs: Self) -> Self }

    // Example 10: Using a protocol as a property type (existential)
    struct Screen { var delegate: Taggable? }
    """,

    # 10. Extension Disambiguation
    "extension_disambiguation": """
    protocol P1 { func execute() }
    protocol P2 { func execute() }

    // Example 1: Class conforming to multiple protocols with same method
    struct Both: P1, P2 {
        func execute() { print("Struct Impl") }
    }
    (Both() as P1).execute()

    // Example 2: Conflict between protocol extension and class implementation
    extension P1 { func execute() { print("P1 Ext") } }
    class C1: P1 {}
    class C2: P1 { func execute() { print("C2 Impl") } }
    C1().execute() // "P1 Ext"
    C2().execute() // "C2 Impl"

    // Example 3: Conflict between protocol extension and conforming type's extension
    protocol Vehicle { func travel() }
    extension Vehicle { func travel() { print("Vehicle traveling") } }
    struct Car: Vehicle {}
    extension Car { func travel() { print("Car traveling") } }
    let car: Vehicle = Car()
    car.travel() // Dispatches to protocol extension, not the struct's extension

    // Example 4: Disambiguation via generic `where` clauses
    extension Array where Element: Equatable { func myFunc() { print("Equatable") } }
    extension Array where Element: Hashable { func myFunc() { print("Hashable") } }

    // Example 5: Disambiguation between modules
    // import ModuleA; import ModuleB; ModuleA.myFunction()

    // Example 6: Conflict between base type method and protocol extension
    extension String { func process() { print("String native") } }
    protocol CustomString { func process() }
    extension CustomString { func process() { print("Protocol ext") } }
    extension String: CustomString {}
    ("hello" as CustomString).process() // "Protocol ext"

    // Example 7: Using associatedtype for complex disambiguation
    protocol C { associatedtype I }; extension C where I == Int { func special() {} }

    // Example 8: Overloading in different extensions
    struct MyType {}
    extension MyType { func handle(value: Int) {} }
    extension MyType { func handle(value: String) {} }

    // Example 9: Overriding a protocol's default implementation
    protocol Greeter { func greet() }
    extension Greeter { func greet() { print("Hello") } }
    struct FriendlyGreeter: Greeter { func greet() { print("Hi there!") } }

    // Example 10: Disambiguating type properties vs instance properties
    struct Disambiguation {
        static var name = "Type Name"
        var name = "Instance Name"
        func printNames() { print(Disambiguation.name, self.name) }
    }
    """,

    # 11. Resource Binding
    "resource_binding": """
    // Example 1: UIImage(named:)
    let icon = UIImage(named: "profile-icon")

    // Example 2: UIStoryboard instantiation
    let storyboard = UIStoryboard(name: "Main", bundle: nil)
    let vc = storyboard.instantiateViewController(withIdentifier: "ProfileViewController")

    // Example 3: LocalizedString
    let title = NSLocalizedString("app_title", comment: "The title of the app")

    // Example 4: Type-safe resources (e.g., R.swift) - conceptual
    // let image = R.image.profileIcon()
    // let color = R.color.primaryColor()

    // Example 5: Loading data from a Plist file
    var config: [String: Any]?
    if let path = Bundle.main.path(forResource: "Config", ofType: "plist") {
        config = NSDictionary(contentsOfFile: path) as? [String: Any]
    }

    // Example 6: Loading and decoding a local JSON file
    if let url = Bundle.main.url(forResource: "data", withExtension: "json") {
        let data = try? Data(contentsOf: url)
        // ... then decode with JSONDecoder
    }

    // Example 7: Using a custom font
    let customFont = UIFont(name: "MyCustomFont-Regular", size: 16.0)

    // Example 8: Loading a CoreData model file (.xcdatamodeld)
    let modelURL = Bundle.main.url(forResource: "MyModel", withExtension: "momd")!
    let managedObjectModel = NSManagedObjectModel(contentsOf: modelURL)!

    // Example 9: Loading a Metal shader function
    // let defaultLibrary = device.makeDefaultLibrary()!
    // let kernelFunction = defaultLibrary.makeFunction(name: "myShader")

    // Example 10: In-app purchase product identifiers
    // SKProductsRequest(productIdentifiers: ["com.myapp.premium_subscription"])
    """,

    # 12. Stringly-Typed API
    "stringly_typed_api": """
    // Example 1: Notification.Name
    NotificationCenter.default.post(name: Notification.Name("userDidLogin"), object: nil)

    // Example 2: UserDefaults keys
    UserDefaults.standard.set("Alice", forKey: "currentUserName")

    // Example 3: Dictionary keys
    var userInfo: [String: Any] = ["userId": 123, "isPremium": true]

    // Example 4: Segue Identifiers
    // performSegue(withIdentifier: "showDetailSegue", sender: self)

    // Example 5: REST API endpoint string construction
    let baseURL = "https://api.example.com"
    let endpoint = "/users/\\(userId)/profile"
    let fullURL = URL(string: baseURL + endpoint)

    // Example 6: Analytics event names
    // Analytics.logEvent("screen_view", parameters: ["screen_name": "Settings"])

    // Example 7: Feature Flag keys
    // if FeatureFlags.isEnabled("new-onboarding-flow") { ... }

    // Example 8: Raw database query strings
    let query = "SELECT * FROM users WHERE age > \\(minAge)"

    // Example 9: KVC (Key-Value Coding)
    let person = Person()
    person.setValue("Bob", forKey: "name")

    // Example 10: Dynamic method invocation via Objective-C runtime
    // perform(Selector("aDynamicMethodName"))
    """,

    # 13. External Contract
    "external_contract": """
    // Example 1: API call with a 3rd party library (Alamofire)
    import Alamofire
    AF.request("https://api.example.com/data").responseJSON { _ in }

    // Example 2: Initializing a 3rd party SDK
    import Firebase
    FirebaseApp.configure()

    // Example 3: Parsing a JSON response
    struct User: Decodable { let id: Int; let name: String }
    // let user = try JSONDecoder().decode(User.self, from: jsonData)
    // This breaks if the server changes 'name' to 'username'

    // Example 4: Webview and JavaScript interface
    // webView.evaluateJavaScript("myJSFunction('data from swift')")

    // Example 5: Inter-app communication via URL Schemes
    // UIApplication.shared.open(URL(string: "otherapp://action?id=123")!)

    // Example 6: Shared UserDefaults via App Groups
    // let sharedDefaults = UserDefaults(suiteName: "group.com.myapp.shared")

    // Example 7: Shared Keychain data
    // KeychainWrapper.standard.set("secret", forKey: "apiToken")

    // Example 8: Bluetooth LE (BLE) communication protocol
    // let serviceUUID = CBUUID(string: "1234")
    // peripheral.writeValue(data, for: characteristic, type: .withResponse)

    // Example 9: Push notification payload
    // let aps = payload["aps"] as? [String: Any]
    // let alert = aps?["alert"] as? String

    // Example 10: Data exchange with App Clips / Widgets
    // File sharing via App Groups
    """,

    # 14. UI State Wrapper
    "ui_state_wrapper": """
    import SwiftUI
    import Combine

    // Example 1: @State and @Binding
    struct EditView: View { @State private var draft = ""; var body: some View { TextField("Draft", text: $draft) } }

    // Example 2: @ObservedObject and @Published
    class Settings: ObservableObject { @Published var notificationsEnabled = true }
    struct SettingsToggle: View { @ObservedObject var settings: Settings; var body: some View { Toggle("Enable", isOn: $settings.notificationsEnabled) } }

    // Example 3: @StateObject
    struct ContainerView: View { @StateObject private var settings = Settings() }

    // Example 4: @EnvironmentObject
    struct InnerView: View { @EnvironmentObject var settings: Settings }

    // Example 5: TCA-like pattern (The Composable Architecture)
    // struct AppState { var count = 0 }
    // enum AppAction { case increment, decrement }
    // let store = Store(initialState: AppState(), reducer: reducer)

    // Example 6: @FocusState
    struct FormView: View {
        enum Field { case name, email }
        @FocusState private var focusedField: Field?
    }

    // Example 7: @GestureState
    // var body: some View {
    //     Image(systemName: "circle").scaleEffect(scale)
    //         .gesture(MagnificationGesture().updating($scale) { ... })
    // }

    // Example 8: Redux-like pattern (e.g., ReSwift)
    // final class AppStore: Store<AppState> { ... }

    // Example 9: MVVM ViewModel
    class MyViewModel: ObservableObject {
        @Published var items: [String] = []
        func fetch() { /* ... */ }
    }

    // Example 10: Manual state management with Combine
    class ManualState: ObservableObject {
        var name = CurrentValueSubject<String, Never>("")
        let objectWillChange = PassthroughSubject<Void, Never>()
    }
    """,

    # 15. Concurrency Attributes
    "concurrency_attr": """
    import Foundation

    // Example 1: Basic async/await
    func downloadImage(url: URL) async throws -> UIImage { ... }

    // Example 2: Task Group
    await withTaskGroup(of: Data.self) { group in
        for url in urls {
            group.addTask { await download(url) }
        }
    }

    // Example 3: @MainActor
    @MainActor
    class UIViewModel: ObservableObject {
        @Published var image: UIImage?
        func updateImage() { self.image = ... }
    }

    // Example 4: Actor
    actor Counter {
        private var value = 0
        func increment() -> Int {
            value += 1
            return value
        }
    }

    // Example 5: `nonisolated`
    extension Counter {
        nonisolated func getID() -> UUID { return id }
    }

    // Example 6: @Sendable closure
    let sendableClosure: @Sendable () -> Void = { ... }
    Task.detached(priority: .background, operation: sendableClosure)

    // Example 7: Task.detached
    Task.detached {
        // This runs on a background thread.
    }

    // Example 8: AsyncStream
    func eventStream() -> AsyncStream<Int> {
        AsyncStream { continuation in
            // ...
            continuation.yield(1)
            continuation.finish()
        }
    }

    // Example 9: Structured concurrency cancellation check
    // try Task.checkCancellation()

    // Example 10: Global Actor
    @globalActor
    struct MyGlobalActor {
        static let shared = MyActor()
        actor MyActor {}
    }

    @MyGlobalActor
    func doSomethingOnGlobalActor() {}
    """
}

# --- 1. API가 요구하는 최종 프롬프트의 '껍데기' 구조 ---
# user의 content는 API 규격에 따라 반드시 '문자열'이어야 하므로, 비워둡니다.
BASE_PROMPT_STRUCTURE = {
    "messages": [
        {
            "role": "system",
            "content": "You are a principal engineer with 15 years of experience specializing in adversarial code generation for Swift obfuscators. Your mission is to architect and generate worst-case scenario Swift source code by strategically combining language patterns known to create ambiguity, conflicts, and edge cases for static analysis engines. The code you produce is the ultimate stress test, designed to probe for weaknesses and maximize the potential for failure in any given obfuscation tool."
        },
        {
            "role": "user",
            "content": ""  # <--- 최종적으로 완성된 JSON 문자열이 들어갈 자리
        }
    ]
}

# --- 2. 'content'에 들어갈 내용물의 '틀'을 파이썬 딕셔너리로 정의 ---
# 이 방식은 JSON 문법 오류를 원천적으로 방지합니다.
USER_CONTENT_TEMPLATE = {
    "task": f"Here is a list of major patterns that complicate Swift obfuscation analysis: {json.dumps(OBFUSCATION_EXCLUSION_PATTERNS)}. From this list, organically combine the patterns specified in the `parameters.patterns` array to generate a single, complex, and syntactically valid Swift source code file. Refer to the `examples` below to understand the meaning of each pattern and how to combine them.",
    "parameters": {
        "patterns": []  # This will be filled dynamically
    },
    "examples": {},  # This will be filled dynamically
    "constraints": [
        {
            "constraint": "Mandatory Use of Examples",
            "description": "For each pattern from the `parameters.patterns` list, you MUST incorporate at least THREE distinct techniques or structures demonstrated in its corresponding example from the `examples` section. This is a critical requirement."
        },
        # ... (나머지 모든 constraints 내용은 여기에 그대로 들어갑니다) ...
        {
            "constraint": "Compilation Requirement",
            "description": "The code must be fully functional and compile without any errors or warnings using Swift 5.7 or later."
        }
    ],
    "output_format": {
        "format": "Raw Swift Code Only",
        "instruction": "CRUCIAL: Your entire response MUST BE only the raw Swift source code string. Do NOT include any explanations, introductory text, or markdown syntax like ```swift ... ```. The output must start directly with `import ...` or the first line of code."
    }
}


# --- 3. 딕셔너리를 직접 조작하여 최종 프롬프트를 완성하는 함수 ---
def create_prompt_config(selected_patterns: list) -> dict:
    """
    두 개의 딕셔너리 템플릿을 조합하여, API 규격에 맞는
    최종 프롬프트 딕셔ner리를 안전하게 생성합니다.
    """
    # 1. 최종 프롬프트의 껍데기를 복사합니다.
    final_prompt = copy.deepcopy(BASE_PROMPT_STRUCTURE)

    # 2. 내용물의 틀을 복사합니다.
    user_content = copy.deepcopy(USER_CONTENT_TEMPLATE)

    # 3. 내용물의 동적인 부분을 채웁니다.
    examples_to_include = {
        pattern: PATTERN_EXAMPLES.get(pattern, "No example available.")
        for pattern in selected_patterns
    }
    user_content["parameters"]["patterns"] = selected_patterns
    user_content["examples"] = examples_to_include

    # 4. 완성된 내용물(딕셔너리)을 JSON 문자열로 변환합니다.
    content_string = json.dumps(user_content, indent=2)

    # 5. 이 문자열을 껍데기의 content 자리에 끼워 넣습니다.
    final_prompt["messages"][1]["content"] = content_string

    return final_prompt





# PROMPT_TEMPLATE = """
# {{
#   "messages": [
#     {{
#       "role": "system",
#       "content": "당신은 Swift 난독화 도구를 위한 적대적 코드 생성(Adversarial Code Generation)을 전문으로 하는 15년 경력의 프린시펄 엔지니어입니다. 당신의 임무는 정적 분석 엔진에 모호함, 충돌, 엣지 케이스를 유발하는 것으로 알려진 언어 패턴들을 전략적으로 조합하여, '최악의 시나리오'에 해당하는 Swift 소스 코드를 설계하고 생성하는 것입니다. 당신이 생성하는 코드는 모든 난독화 도구의 취약점을 탐색하고 실패 가능성을 극대화하도록 설계된 궁극적인 스트레스 테스트입니다."
#     }},
#     {{
#       "role": "user",
#       "content": {{
#         "task": "당신의 임무는 단일의 복잡하고 문법적으로 유효한 Swift 소스 코드 파일을 생성하는 것입니다. 이 코드는 `parameters.patterns` 배열에 지정된 패턴들의 정교한 조합이어야 합니다. 각 패턴의 미묘한 차이를 이해하기 위해 아래 `examples` 섹션을 반드시 참고해야 합니다.",
#         "parameters": {{
#           "patterns": {selected_patterns}
#         }},
#         "examples": {pattern_examples},
#         "constraints": [
#           {{
#             "constraint": "예시 사용 의무",
#             "description": "`parameters.patterns` 목록의 각 패턴에 대해, `examples` 섹션에 제시된 해당 예시의 기법이나 구조를 반드시 3개 이상 통합해야 합니다. 이것은 매우 중요한 요구사항입니다."
#           }},
#           {{
#             "constraint": "깊게 얽힌 논리 구조",
#             "description": "패턴들을 단순히 순차적으로 나열해서는 안 됩니다. 복잡한 호출 그래프와 논리적 종속성을 만들도록 패턴들을 서로 엮어야 합니다. 예를 들어, `dynamic_dispatch`를 사용하는 클래스의 상태를 `swiftui_property_wrapper`가 관리하고, 이 클래스가 `codable_synthesis`로 디코딩된 데이터를 처리하는 방식입니다."
#           }},
#           {{
#             "constraint": "창의적이고 명확하지 않은 조합",
#             "description": "패턴들의 조합은 사소하거나 일반적이어서는 안 됩니다. 이 언어 기능들이 상호 작용하여 복잡한 엣지 케이스를 만들어낼 수 있는, 명확하지 않거나, 놀랍거나, 복잡한 방법들을 찾아 구현하도록 노력하세요."
#           }},
#           {{
#             "constraint": "구조적 다양성",
#             "description": "만약 동일한 파라미터로 이 프롬프트가 여러 번 주어진다면, 생성된 각 결과물은 구조적으로나 개념적으로 달라야 합니다. 상용구(boilerplate)나 반복적인 구조를 생성하는 것을 피하세요."
#           }},
#           {{
#             "constraint": "현실적이고 독립적인 코드",
#             "description": "생성된 코드는 현실적인 애플리케이션 시나리오를 반영해야 합니다. 사소하거나 학술적인 예제는 피해야 합니다. 최종 결과물은 `import SwiftUI`와 같이 필요한 모든 import 구문을 포함한, 단일의 독립적인 코드 블록이어야 합니다."
#           }},
#           {{
#             "constraint": "플레이스홀더 및 주석 금지",
#             "description": "'... 구현 세부 정보 ...'와 같은 플레이스홀더 주석을 엄격히 금지합니다. 최종 코드에는 어떤 종류의 주석도 포함되어서는 안 됩니다."
#           }},
#           {{
#             "constraint": "컴파일 요구사항",
#             "description": "코드는 Swift 5.7 이상 버전에서 어떠한 오류나 경고 없이 완벽하게 컴파일되어야 합니다."
#           }}
#         ],
#         "output_format": {{
#           "format": "순수 Swift 코드만 출력",
#           "instruction": "매우 중요: 당신의 전체 답변은 반드시 순수한 Swift 소스 코드 문자열이어야 합니다. 어떠한 설명, 도입부, 또는 ```swift ... ```와 같은 마크다운 구문도 포함하지 마십시오. 출력은 `import ...` 구문이나 코드의 첫 줄로 바로 시작해야 합니다."
#         }}
#       }}
#     }}
#   ]
# }}
# """
