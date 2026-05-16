# Forms and Validation

### Form Architecture

Forms bind to models via `ng-model`. Validation state is available through properties like `$valid`, `$invalid`, `$dirty`, and `$touched`.

### Named Forms

Name every form to access its controller from the template:

```html
<form name="vm.orderForm" ng-submit="vm.submitOrder()" novalidate>
    <input name="customerName" ng-model="vm.order.customerName" required />
    <div ng-if="vm.orderForm.customerName.$touched && vm.orderForm.customerName.$invalid">
        <span ng-if="vm.orderForm.customerName.$error.required">Required.</span>
    </div>
</form>
```
`novalidate` gives AngularJS full control over validation.

### Custom Validators

Create directives that add to `$validators` or `$asyncValidators` on `ngModelController`:

```javascript
ngModel.$asyncValidators.uniqueUsername = function(value) {
    return UserService.checkUsername(value);
};
```

### Validation Display Timing

Display errors only after user interaction (`$touched && $invalid` or `$dirty && $invalid`).

### Form Submission

Disable the submit button while invalid or submitting. Always handle both success and error paths of the submission promise.

---
[Back to Overview](./OVERVIEW.md)
