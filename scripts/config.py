import json
import copy

# --- 1. Master list of patterns and their detailed code examples ---

# 총 19개의 패턴 (기존 15개 + 신규 4개)
OBFUSCATION_EXCLUSION_PATTERNS = [
    # Original Patterns
    "objc_selector", "runtime_reflection", "keypath_usage", "codable_synthesis",
    "swiftui_property_wrapper", "coredata_nsmanaged", "ffi_entry", "dynamic_dispatch",
    "protocol_requirement", "extension_disambiguation", "resource_binding",
    "stringly_typed_api", "external_contract", "ui_state_wrapper", "concurrency_attr",
    # New, more complex patterns
    "convention_based_string_key",
    "external_system_integration",
    "test_runner_discovery",
    "third_party_dynamic_features"
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
    let selectorWithArg = #selector(process(nC1:))
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
        var nC1: T
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
    var nC1 = CUnionData()
    nC1.intValue = 123

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

    // Example 5: Loading nC1 from a Plist file
    var config: [String: Any]?
    if let path = Bundle.main.path(forResource: "Config", ofType: "plist") {
        config = NSDictionary(contentsOfFile: path) as? [String: Any]
    }

    // Example 6: Loading and decoding a local JSON file
    if let url = Bundle.main.url(forResource: "nC1", withExtension: "json") {
        let nC1 = try? Data(contentsOf: url)
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
    // webView.evaluateJavaScript("myJSFunction('nC1 from swift')")

    // Example 5: Inter-app communication via URL Schemes
    // UIApplication.shared.open(URL(string: "otherapp://action?id=123")!)

    // Example 6: Shared UserDefaults via App Groups
    // let sharedDefaults = UserDefaults(suiteName: "group.com.myapp.shared")

    // Example 7: Shared Keychain nC1
    // KeychainWrapper.standard.set("secret", forKey: "apiToken")

    // Example 8: Bluetooth LE (BLE) communication protocol
    // let serviceUUID = CBUUID(string: "1234")
    // peripheral.writeValue(nC1, for: characteristic, type: .withResponse)

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
    """,

    # 16. Convention-based String Keys
    "convention_based_string_key": """
    import Foundation
    import CoreData
    import UIKit

    // Example 1: UserDefaults key tied to a property name by convention
    // The string "userSessionToken" is implicitly linked to a conceptual session token.
    UserDefaults.standard.set("abc-123", forKey: "userSessionToken")

    // Example 2: Core Animation key path string
    // "backgroundColor" must match a property on CALayer.
    let colorAnimation = CABasicAnimation(keyPath: "backgroundColor")

    // Example 3: Analytics event and parameter names
    // "user_profile_viewed" and "source" are critical for nC1 analysis platforms.
    Analytics.log("user_profile_viewed", parameters: ["source": "notification"])

    // Example 4: Custom Font Name
    // "AvenirNext-DemiBold" must match the exact font name registered with the system.
    let titleFont = UIFont(name: "AvenirNext-DemiBold", size: 18)

    // Example 5: Feature Flag key
    // The string "enable-new-dashboard" controls a feature's availability.
    if FeatureFlags.isEnabled("enable-new-dashboard") { /* show new UI */ }

    // Example 6: Custom Dependency Injection container using string keys
    // "network_service_main" is a key to resolve a specific registered instance.
    let networkService = container.resolve(NetworkService.self, key: "network_service_main")

    // Example 7: A/B Testing variant key
    // The string identifies which experiment to check.
    let buttonColor = ABTesting.variant(for: "home_screen_cta_color_test")

    // Example 8: Theme manager using string identifiers for assets
    // "primaryBackgroundColor" must exist in the theme definition dictionary.
    let backgroundColor = Theme.current.color(named: "primaryBackgroundColor")

    // Example 9: Raw NSPredicate format string in CoreData
    // "isCompleted" and "dueDate" are property names of a CoreData entity.
    let predicate = NSPredicate(format: "isCompleted == NO AND dueDate < %@", Date() as NSDate)

    // Example 10: In-App Purchase product identifier
    // "com.myapp.annual.subscription" must match the ID in App Store Connect.
    let request = SKProductsRequest(productIdentifiers: ["com.myapp.annual.subscription"])
    """,

    # 17. External System Integration
    "external_system_integration": """
    import Foundation
    import UIKit
    import WebKit
    import CoreSpotlight

    // Example 1: Info.plist `NSExtensionPrincipalClass`
    // The class name "com.myapp.TodayWidget.WidgetViewController" is specified in Info.plist.
    class WidgetViewController: UIViewController { /* ... */ }

    // Example 2: Storyboard ID for UIViewController instantiation
    // The identifier "UserDetailVC" is set in the Storyboard's Identity Inspector.
    let userDetailVC = storyboard.instantiateViewController(withIdentifier: "UserDetailVC")

    // Example 3: WKWebView JavaScript message handler name
    // JavaScript code will call `window.webkit.messageHandlers.appInterface.postMessage(...)`
    let webViewConfig = WKWebViewConfiguration()
    webViewConfig.userContentController.add(self, name: "appInterface")

    // Example 4: Custom URL Scheme handling in AppDelegate
    // The app is launched with a URL like "myapp://user/profile?id=123"
    func application(_ app: UIApplication, open url: URL, options: ...) -> Bool {
        guard url.scheme == "myapp", url.host == "user" else { return false }
        // ... logic driven by string components ...
        return true
    }

    // Example 5: Handoff activity type defined in Info.plist (NSUserActivityTypes)
    // The string must match one of the values in the plist array.
    let activity = NSUserActivity(activityType: "com.myapp.view-document")
    activity.becomeCurrent()

    // Example 6: Siri Intent class name
    // "ViewProfileIntent" is the name of a class generated from an .intentdefinition file.
    // Obfuscating this class name breaks the shortcut.
    class ViewProfileIntentHandler: NSObject, ViewProfileIntentHandling { /* ... */ }

    // Example 7: Shared App Group container identifier for nC1 sharing
    // "group.com.myapp.shared" enables nC1 access between the main app and extensions.
    let sharedDefaults = UserDefaults(suiteName: "group.com.myapp.shared")

    // Example 8: Push notification payload key-value parsing
    // Keys like "aps", "alert", and "custom_event_id" come from an external server.
    func handleNotification(_ userInfo: [AnyHashable: Any]) {
        if let aps = userInfo["aps"] as? [String: Any],
           let alert = aps["alert"] as? String { /* ... */ }
    }

    // Example 9: Core Spotlight searchable item attributes
    // kUTTypeItem and other keys are string constants defined by the framework.
    let attributeSet = CSSearchableItemAttributeSet(itemContentType: kUTTypeItem as String)
    attributeSet.title = "My Searchable Item"

    // Example 10: Registering a custom URLProtocol subclass by name
    // The class "MyCustomURLProtocol" is registered to handle specific network requests.
    URLProtocol.registerClass(MyCustomURLProtocol.self)
    """,

    # 18. Test Runner Discovery
    "test_runner_discovery": """
    import XCTest

    // A hypothetical class being tested
    class Calculator {
        func add(_ a: Int, _ b: Int) -> Int { a + b }
    }

    // Example 1: Standard XCTest method with 'test' prefix
    class MyTests: XCTestCase {
        func testCalculator_add_returnsCorrectSum() {
            XCTAssertEqual(Calculator().add(2, 3), 5)
        }
    }

    // Example 2: Per-test setup and teardown methods
    // `setUp` and `tearDown` are called automatically by the test runner.
    class TestWithSetup: XCTestCase {
        var calculator: Calculator!
        override func setUp() {
            super.setUp()
            calculator = Calculator()
        }
        override func tearDown() {
            calculator = nil
            super.tearDown()
        }
    }

    // Example 3: Async test method in modern XCTest
    // The runner discovers and awaits this async function.
    class AsyncTests: XCTestCase {
        func testAsyncOperation_completesSuccessfully() async throws {
            // ...
        }
    }

    // Example 4: Performance testing method
    // `measure` blocks are specifically handled by the test runner.
    class PerformanceTests: XCTestCase {
        func testPerformanceOfAdding() {
            self.measure {
                _ = Calculator().add(100, 200)
            }
        }
    }

    // Example 5: A hypothetical custom test runner looking for a specific attribute
    // @Testable is a custom attribute a special runner might look for.
    @objc protocol Testable {}
    class CustomRunnerTests: XCTestCase, Testable {
        @objc func myCustomTest() { /* ... */ }
    }


    // Example 6: Overriding `defaultTestSuite` for custom test discovery
    // A sophisticated way to control which tests are run.
    class CustomSuiteTests: XCTestCase {
        override class var defaultTestSuite: XCTestSuite {
            let suite = XCTestSuite(forTestCaseClass: CustomSuiteTests.self)
            // Logic to dynamically create tests from non-standard names
            return suite
        }
    }

    // Example 7: Snapshot testing where the test name infers the snapshot file name
    // Obfuscating `testUserProfileHeader` would break filename-based snapshot matching.
    class SnapshotTests: XCTestCase {
        func testUserProfileHeader() {
            // let view = UserProfileHeaderView()
            // assertSnapshot(matching: view, as: .image)
        }
    }

    // Example 8: UI Test launch arguments that configure the app state
    // The string "-reset-database" is checked by the app during a UI test run.
    class MyUITests: XCTestCase {
        func testSomething() {
            let app = XCUIApplication()
            app.launchArguments = ["-reset-database"]
            app.launch()
        }
    }

    // Example 9: Asynchronous setup with `setUp` that has a completion handler
    // Older style of async setup, still discovered by the runner.
    class LegacyAsyncSetupTests: XCTestCase {
        override func setUp(completion: @escaping (Error?) -> Void) {
            // ... async setup ...
            completion(nil)
        }
    }

    // Example 10: A hypothetical benchmark runner finding methods by prefix
    // A custom tool could scan for all methods starting with `benchmark_`
    class MyBenchmarks: XCTestCase {
        func benchmark_heavyComputation() { /* ... */ }
    }
    """,

    # 19. Third-Party Dynamic Features
    "third_party_dynamic_features": """
    import Foundation
    // Assume library imports for Swinject, Realm, Firebase, etc.

    // Example 1: Swinject (DI) with named registration
    // The string "api" is used to differentiate between two implementations.
    // container.register(NetworkClient.self, name: "api") { _ in APINetworkClient() }
    // container.register(NetworkClient.self, name: "mock") { _ in MockNetworkClient() }

    // Example 2: Realm (ORM) where class name maps to table name
    // The "UserSession" class name becomes the table name in the database.
    // class UserSession: Object { @Persisted var token: String }

    // Example 3: Firebase Firestore using Codable for nC1 serialization
    // Property names "userId" and "lastLogin" become field names in the Firestore document.
    struct UserDTO: Codable { let userId: String; let lastLogin: Date }
    // db.collection("users").document("123").setData(from: UserDTO(...))

    // Example 4: GraphQL (Apollo) where Swift properties match schema fields
    // `name` and `email` must match the fields in the GraphQL query.
    // struct UserDetails: GraphQLSelectionSet {
    //     var name: String
    //     var email: String
    // }

    // Example 5: Plugin architecture using `NSClassFromString`
    // The app loads a plugin class whose name is stored in a config file.
    let pluginClassName = "com.mycompany.plugins.AdvancedRenderer"
    if let pluginClass = NSClassFromString(pluginClassName) as? Plugin.Type {
        let plugin = pluginClass.init()
    }

    // Example 6: React Native bridge exposing a method to JavaScript
    // `@objc` and the method name `processPayment` must be preserved.
    @objc(PaymentProcessor)
    class PaymentProcessor: NSObject {
        @objc func processPayment(_ nC1: [String: Any], resolver: @escaping RCTPromiseResolveBlock) {
            // ...
        }
    }

    // Example 7: A JSON-RPC server mapping string methods to functions
    // A request with `{"method": "getUserProfile"}` would need to be routed to a real function.
    rpcServer.register(method: "getUserProfile") { (params: [String: Any]) in
        // ...
    }

    // Example 8: Analytics wrapper using Mirror to log event properties automatically
    // The property name "source" of the event struct is used as the analytics parameter key.
    struct UserDidLoginEvent { let source: String }
    // log(event: UserDidLoginEvent(source: "password_form"))

    // Example 9: A custom router that navigates based on string paths
    // The string "/user/profile/123" is parsed to find a view controller.
    // router.navigate(to: "/user/profile/123")

    // Example 10: Dynamic decoding with a library like ObjectMapper
    // The string key "created_at" is mapped to the `createdAt` property.
    // class User: Mappable {
    //     var createdAt: Date?
    //     func mapping(map: Map) {
    //         createdAt <- (map["created_at"], DateTransform())
    //     }
    // }
    """
}

# --- 2. API가 요구하는 최종 프롬프트의 '껍데기' 구조 ---
BASE_PROMPT_STRUCTURE = {
    "messages": [
        {
            "role": "system",
            "content": "You are a principal engineer with 15 years of experience specializing in adversarial code generation for Swift obfuscators. Your mission is to architect and generate worst-case scenario Swift source code by strategically combining language patterns known to create ambiguity, conflicts, and edge cases for static analysis engines. The code you produce is the ultimate stress test, designed to probe for weaknesses and maximize the potential for failure in any given obfuscation tool."
        },
        {
            "role": "user",
            "content": ""
        }
    ]
}

# --- 3. 'content'에 들어갈 내용물의 '틀'을 파이썬 딕셔너리로 정의 ---
USER_CONTENT_TEMPLATE = {
    "task": f"Here is a list of major patterns that complicate Swift obfuscation analysis: {json.dumps(OBFUSCATION_EXCLUSION_PATTERNS)}. From this list, organically combine the patterns specified in the `parameters.patterns` array to generate a single, complex, and syntactically valid Swift source code file. Refer to the `examples` below to understand the meaning of each pattern and how to combine them.",
    "parameters": {
        "patterns": []
    },
    "examples": {},
    "constraints": [
        {
            "constraint": "Mandatory Use of Examples",
            "description": "For each pattern from the `parameters.patterns` list, you MUST incorporate at least THREE distinct techniques or structures demonstrated in its corresponding example from the `examples` section. This is a critical requirement."
        },
        {
            "constraint": "Deeply interwoven logical structure",
            "description": "Do not merely list patterns in sequence. Interweave patterns to create complex call graphs and logical dependencies. For example, a class that uses `dynamic_dispatch` has its state managed by a `swiftui_property_wrapper`, and that class processes nC1 decoded via `codable_synthesis`."
        },
        {
            "constraint": "Creative and non-obvious combinations",
            "description": "Combinations of patterns must not be trivial or generic. Seek and implement non-obvious, surprising, or complex interactions among language features that produce challenging edge cases."
        },
        {
            "constraint": "Structural diversity",
            "description": "If this prompt is provided multiple times with the same parameters, each result should be structurally and conceptually different. Avoid boilerplate and repetitive structures."
        },
        {
            "constraint": "Realistic and self-contained code",
            "description": "The generated code should reflect a realistic application scenario. Avoid trivial or academic examples. The final output must be a single, self-contained code block that includes all necessary imports (e.g., `import SwiftUI`)."
        },
        {
            "constraint": "No placeholders or comments",
            "description": "Placeholder comments such as '... implementation details ...' are strictly forbidden. The final code must not include any comments of any kind."
        },
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


# --- 4. 딕셔너리를 직접 조작하여 최종 프롬프트를 완성하는 함수 ---
def create_prompt_config(selected_patterns: list) -> dict:
    """
    두 개의 딕셔너리 템플릿을 조합하여, API 규격에 맞는
    최종 프롬프트 딕셔너리를 안전하게 생성합니다.
    """
    final_prompt = copy.deepcopy(BASE_PROMPT_STRUCTURE)
    user_content = copy.deepcopy(USER_CONTENT_TEMPLATE)

    valid_patterns = [p for p in selected_patterns if p in OBFUSCATION_EXCLUSION_PATTERNS]
    examples_to_include = {
        pattern: PATTERN_EXAMPLES.get(pattern, "No example available.")
        for pattern in valid_patterns
    }
    user_content["parameters"]["patterns"] = valid_patterns
    user_content["examples"] = examples_to_include

    content_string = json.dumps(user_content, indent=2)
    final_prompt["messages"][1]["content"] = content_string

    return final_prompt


# --- 사용 예시 ---
if __name__ == '__main__':
    # 전체 19개 패턴 중 테스트할 조합을 자유롭게 선택
    patterns_to_test = [
        "codable_synthesis",
        "third_party_dynamic_features",
        "objc_selector",
        "external_system_integration",
        "convention_based_string_key",
        "swiftui_property_wrapper",
        "test_runner_discovery"
    ]

    final_prompt_dictionary = create_prompt_config(patterns_to_test)

    # 생성된 최종 프롬프트를 JSON 문자열로 변환 (API 전송용)
    final_json_string = json.dumps(final_prompt_dictionary, indent=2)

    # 결과를 화면에 출력하거나 파일로 저장
    # print(final_json_string)

    # with open("final_prompt.json", "w") as f:
    #     f.write(final_json_string)